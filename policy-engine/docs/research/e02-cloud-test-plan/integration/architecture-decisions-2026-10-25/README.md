# E02: Fabric runtime-аннотации и native preflight — решения G для реализации

25 октября 2026. `architecture_selection=selected_by_G`, `code_acceptance=false`, `closure_ids=[]`. Это архитектурный ответ на [пакет 8533003b](https://github.com/DenisKopylov/polisyos/blob/8533003b91961cf9ba1305ec296dab7f3ed40e4b/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/g-questions/native-exceptions-20261025/README.md), а не новая приёмка E02. Source вопроса — `49dff9183c20be3877d47953e0142417cb854cd0`; G documentation branch не заменяет source исполнителя.

**Выбран A: сохранить разрешение типов в рантайме, точно определить поддерживаемые объекты и сузить lint-исключения.** Перенос импортов под `TYPE_CHECKING` ради зелёного Ruff здесь не является достаточным исправлением. Новые reflection framework, registry или facade wrappers не нужны.

Независимая проверка уточнила исходный scope:

- 14 диагностик — это 14 импортных bindings, а не 14 API. Исходные 11 спорных bindings представлены шестью callables.
- Для десяти из этих bindings подтверждён путь через поддерживаемые фасады. `ConnectionConfig` используется в четырёх документированных mode-функциях, которые не экспортируются через `data_plane` facade. Их текущее поведение сохраняется как отдельная ограниченная совместимость; новый public-stable export не создаётся.
- Полная затронутая публичная поверхность шире контрольных примеров пакета: восемь callables и поля `WorldQueryRequest`. Добавлены второй конструктор invalidation, `query_claims`, `query_events` и request-class. Уже выбранный `ConnectorMetadataSpec` остаётся отдельным существующим обязательством.

**Редакция R2:** самостоятельное review усилило независимый compatibility oracle, alias-owner checks и import custody. Добавлен разбор expiry obligations на source `8533003b`: **27 записей, 8 потоков**. Это source-bound metadata census, не новый native run; исторические 82/61 не являются текущей очередью.

Читать в порядке:

1. [01 — выбранный контракт, полный scope и границы расширения](01-fabric-runtime-annotations.md).
2. [02 — последовательность реализации, companions и содержательные проверки](02-implementation-and-verification.md).
3. [03 — исследования, редтим, самостоятельное review и пределы доказательств](03-research-and-review.md).
4. [04 — самостоятельный критический разбор R2](04-independent-review-r2.md).
5. [05 — решения для всех текущих native expiry records](05-native-preflight-expiry-decisions.md): dynamic imports, operational coverage, Fabric/IR Ruff и mypy, discovery/runtime naming.
6. [inputs.json](inputs.json) — неизменённые identities и receipts R1; [native-preflight-inputs.json](native-preflight-inputs.json) — census R2 и полная маршрутизация 27 records.

Исполнитель может начинать scoped implementation без нового общего запроса «нужен выбор G». Это решение не меняет G528, семь N818 exception identities, научные/правовые основания, product statuses или system-design-decisions. Нового global freeze нет. Реализация, её actual receipts и formal closure остаются отдельными этапами.
