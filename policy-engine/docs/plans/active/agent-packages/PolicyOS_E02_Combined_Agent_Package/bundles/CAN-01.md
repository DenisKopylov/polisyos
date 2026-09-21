# CAN-01 — Strict canon: один primitive, явные Core/IR профили

**E02 · окно CP2 · локальная проверка L · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-021 (M).

**Предшественники:** Нет. **Совместная очередь:** LANE-06.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Снять golden byte/error corpus двух кодеков; выделить общую строгую механику в нейтральный common/canonical.py и при нужде hashing.py. Core/IR фасады сохраняют намеренно разные typed-tag profiles, exception identity и historical version ABI. Отдельно определить несовпадение возможностей под одной 0.2.0 identity, не расширять IR decoder молча.

**Различающие тесты и сохраняемое поведение.** Decimal/date/bytes/null/numeric/depth/tags, float_hex/bytes_hex/array_digest, malformed input, old read/write/hash identity. Идентичные исторические payloads не меняют digest. IR не импортирует Core; runtime JsonDataVisitor/WIRE-01 остаются отдельными contracts.

**Не считать исправлением.** Не переписывать CAS IDs, не применять широкий новый default к old blobs, не объявлять Core единственным правильным профилем и не сливать все serializers.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-021:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **CAN-01**; необходимые пакеты: CAN-01.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/common/canonical.py
policy-engine/src/polisyos/common/hashing.py
policy-engine/src/polisyos/core/canon/canon_json.py
policy-engine/src/polisyos/core/canon/hashing.py
policy-engine/src/polisyos/ir/model_layer/canon.py
```

**Читать как соседние контракты:**

```text
policy-engine/architecture/imports/policy.toml
policy-engine/src/polisyos/common/serialization.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_can_01.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** Нет по статической карте. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-11. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Условия общего использования:**

**A18.** Изменение import-пути не меняет historical bytes/format/ошибки автоматически. Relocation, исправление поведения и прекращение поддержки получают раздельные результаты.

**Ресурс:** L — I1 broker admits requests against a shared seven-unit L-equivalent budget and at most seven resource-bearing process groups across all worktrees; resource cost is micro=0.5, standard=1, measured medium=2–3. Permit is released after process-group cleanup and receipt; review does not hold it. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без compute permit. Named shared resources and immutable request fields remain enforced; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-021

Источник LA_r09, строки 990–1021; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-021 -->
## LA-021. Два канонических кодека с одной версией и разными возможностями

Слияние / разделение ответственности

**Статус.** Дублирование реализации и расхождение принятого формата подтверждены.

**Точная область:**

`src/polisyos/ir/model_layer/canon.py`

`src/polisyos/core/canon/canon_json.py`

`src/polisyos/core/canon/hashing.py`

**Что установлено и почему это legacy.** IR содержит собственные CanonSpec, encoder/decoder и raw hashing. Core повторяет ту же механику, но дополнительно понимает float_hex, bytes_hex и array_digest. Обе CanonSpec по умолчанию объявляют polisyos.canon.json@0.2.0. На десяти обычных значениях bytes и обратное чтение совпали; три дополнительных tag-формата Core принимает, а IR отвергает при записи и чтении. Это не доказательство, что любой исторический IR должен их принимать: это несогласованное владение общей реализацией и профилем.

**Что сохранить.** Побайтовые правила уже сохранённых объектов; strict checks, глубину, Decimal, даты, bytes, float-политику, варианты hashing и их предупреждения. Различить общий алгоритм и намеренно более узкий IR-профиль. Исключения в двух модулях сейчас имеют разные Python identity — это тоже миграционное обязательство.

**Куда перенести / с чем объединить.** Предлагаемый нейтральный common/canonical.py для общей механики и, при необходимости, common/hashing.py для raw byte primitives; существующие Core/IR фасады сохраняют разрешённые профили. Это новые предлагаемые файлы, не уже готовая третья библиотека. Прямой импорт Core из IR противоречит прочитанной матрице направлений; Common доступен обоим.

**Порядок миграции.** Начать с golden byte corpus и выделения действительно одинаковых primitives. Затем связать encoder/decoder с явным профилем и совместимостью версии, сохранив текущие адреса на переход. Расширение формата оформлять отдельно; не переписывать CAS IDs и не подменять historical decoder новым широким default. Обычную common.serialization не сливать со строгим каноном.

**Приёмка.** Проверить двустороннее чтение поддержанных старых payloads, byte/hash identity, типы исключений, numeric/date/null/typed-tag cases, depth errors и imports. Локальный десятиэлементный корпус — начало characterization, а не доказательство полной эквивалентности всех структур.

**Приоритет.** Высокая архитектурная отдача; средняя/высокая цена из-за persisted-format ABI. После локальных очисток.

**Граница вывода.** Не установлен конкретный повреждённый production-артефакт. Core сам по себе не объявляется единственным правильным профилем. Общая реализация не даёт права незаметно расширить принятые типы IR.

**Основания.** E45, E46, E47, E48, E64. P06–P10; два полных кодека сверены и исполнены с настоящим Pydantic.

<!-- PAGEBREAK -->

<!-- SOURCE_END LA:LA-021 -->

## Защищённые различения исходного legacy-аудита

LK — активный идентификатор защиты; внутри сохранены исходные K-заголовки.

<!-- SOURCE_BEGIN LK:LK07 -->
## K07. Runtime JSON и строгий канон — разные контракты

common.serialization.JsonDataVisitor служит JSON-safe преобразованию runtime values и имеет собственные cycle/depth/unsupported policies. Строгий канон участвует в устойчивой идентичности и typed round-trip. LA-021 объединяет две копии строгой механики, а не все сериализаторы по сходству имени. [E45, E46, E64]

<!-- SOURCE_END LK:LK07 -->

<!-- SOURCE_BEGIN LK:LK20 -->
## K20. Content identity и контрольная сумма не являются сами по себе разрешением на reuse или closeout

Generation basis действительно строится из переданных bytes и версии правила; локально проверены current, changed content/model/rule, malformed digest и missing record. Но он не может самостоятельно установить полноту перечня, который передал caller. Generic manifest checker, в свою очередь, сохраняет поддержку пустого expected hash и не удостоверяет обязательность состава. Эти модули — полезные узкие primitives, **не obsolete helpers и не готовая полная replacement policy**. [E144, E146; r05-P34–P42]

В LA-039/LA-040/LA-041 их объединение должно сохранить различие: истинность hash, текущая принадлежность к поколению, эквивалентность запроса, целостность выходов и допустимость использования — разные утверждения. Ни одно из них не заменяется названием `current`, одним файлом manifest или удачным return code.

<!-- SOURCE_END LK:LK20 -->

