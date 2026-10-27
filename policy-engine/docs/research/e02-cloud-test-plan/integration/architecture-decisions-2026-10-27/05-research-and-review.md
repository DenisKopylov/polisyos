# Исследование, adversarial review и границы результата

## Первичные источники и применимость

| Источник | Что использовано | Чего из него не выводим |
|---|---|---|
| [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259.html) | JSON objects — string-keyed data; `_type` не имеет встроенной семантики. Value roundtrip отличается от byte custody. | JSON сам не решает native Decimal/date/bytes transport. |
| [RFC 8785 / JCS](https://www.rfc-editor.org/rfc/rfc8785.html) | Canonical bytes требуют определённой value domain и однозначной serialization law. | Не импортируем JCS number/Unicode law в существующий PolicyOS codec и не называем его JCS-compliant. |
| [RFC 8949 / CBOR](https://www.rfc-editor.org/rfc/rfc8949.html) | Maps и tagged values могут быть структурно разными сущностями. Полезный precedent для явной grammar. | Не предлагаем CBOR migration или автоматическое доверие неизвестным tags. |
| [MongoDB Extended JSON, accepted specification](https://github.com/mongodb/specifications/blob/master/source/extended-json/extended-json.md#restrictions-and-limitations) | Раздел Restrictions and limitations прямо описывает неразличимость wrapper-shaped documents при отсутствии escape. Это реальный пример слабости “узнать tag по shape”. | MongoDB parser rules не становятся PolicyOS type/authority policy. |
| [XTDB: Time in XTDB](https://docs.xtdb.com/about/time-in-xtdb.html) | Valid и system/transaction axes независимы; late corrections и future-effective facts объясняют, зачем сохранять конкретный cursor. | Не переносим implicit “now” defaults или весь XTDB в Runtime. Future-valid не является forecast. |
| [RFC 3339](https://www.rfc-editor.org/rfc/rfc3339.html) | Qualified timestamp/offset; unknown local offset не означает неизвестный UTC instant. | Стандарт не задаёт legal dates, policy periods, owner retention или authority. |
| [OpenAPI 3.1.2](https://spec.openapis.org/oas/v3.1.2.html) | Required property и nullable value — разные измерения schema. Presence law надо выразить в DTO и clients. | Не требуется менять версию OpenAPI/toolchain ради этой работы. |
| [SQL Server: temporal history retention](https://learn.microsoft.com/en-us/sql/relational-databases/tables/temporal/manage-retention?view=sql-server-ver17) | Historical query может утратить воспроизводимость из-за history retention; unavailable нельзя подменять current/empty. | Этот system-time пример не доказывает bitemporal semantics или необходимость бесконечного хранения. |

Это evidence для выбора подходов, а не ссылка на единственный “SOTA стандарт”. Наиболее подходящее решение здесь — структурная grammar, immutable selected-view identities и explicit owner semantics, реализованные существующими механизмами. Новая технология не нужна ради самого названия.

## Работа прямых помощников

Работали шесть direct reviewers/researchers без детей, source writes, product imports или tests:

| Роль | Существенный результат | Решение G |
|---|---|---|
| CAN owner research | Найдены pre-encoder alias, state/cache/checkpoint consumers и независимый idempotency key law. | Включены в обязательный footprint; codec-only fix недостаточен. |
| CAN primary research | Namespace escape всей `_type` области устойчивее списка сегодняшних tags. | Принято; structural extension без wrapping всех обычных maps. |
| CAN redteam | Нет real version dispatch; dataclass bypass; array/hex re-encode ambiguity; несортированные entries; fallback/cache escape. | Устранено в решении до реализации; отдельные C03–C14 falsifiers. |
| TC owner research | Пять TemporalScope fields, actual non-CAS slots, request snapshot versions и existing GET path. | Сохранены все selectors; нет “все refs — CAS”; snapshot v3 обязателен. |
| TC primary research | Independent axes, partial scope, retention и distinction request/evidence time. | Нет universal mandatory bundle или now default; typed unavailable и per-consumer adequacy. |
| TC redteam | DTO-only потеря поля; bare digest equality; evidence_input_refs omitted; authority helpers не recompute. | Class-wide v2 closure, actual resolver и scorecard/role/seal companions, не один дополнительный profile field. |

## Самостоятельный review G: изменения после первичных рекомендаций

**R-CAN-1 — signed zero.** Совет заменить Foundry hex projections обычными floats не принят буквально. Source `_canonical_float_repr` нормализует оба zero в `"0"`, а Foundry `float.hex()` различает знак. Выбраны bounded Core representation carriers для hex/array; они не выдаются за generic primitives и re-emit свою canonical форму. Existing flags проверяются, carrier не даёт bypass.

**R-CAN-2 — cache version недостаточно “по желанию”.** Version domain обязателен, не только условная очистка cache: new native bytes могут совпадать со старым colliding key. Existing generation fence дополнительно закрывает in-flight old writer. Durable node retry отделён от disposable memoization, чтобы новая law не удваивала side effects.

**R-CAN-3 — decoder conformance.** Одного `mapping/entries` недостаточно: sorted pairs, duplicate/extra-field rejection, no double dispatch, wrapper noncanonical для map без `_type`, logical vs wire depth, dataclass projection и declared-version decoder входят в единую law. `.2` неизменен.

**R-TC-1 — присутствие и adequacy.** Omitted scope сохраняет legacy; explicit top null/empty отказывают; partial nonempty допускается без обязательных двух timestamp. Explicit inner null сохраняется. Producer доказывает запись authorized selection, а фактический data consumer отдельно доказывает применение. Это не одно событие.

**R-TC-2 — snapshot migration.** Проверены manual field lists в `job_attempt_publication.py`. Новое default-null поле могло сломать старые request hashes или потеряться при queue validation. Установлен v3 wire при выбранном scope и точная v1/v2 projection без нового поля.

**R-TC-3 — полный identity denominator.** `evidence_input_refs` отсутствует в current identity tuple; scalar refs не кодируют CAS/non-CAS domain. V2 связывает весь owner-defined basis, пересчитывает digest, сравнивает actual consumption и не включает собственные output/seal refs. Closure equality и authority/temporal adequacy разделены.

**R-TC-4 — никакого искусственного общего барьера.** Независимая Lex boundary сохранена; TC не ждёт CAN `.3`; readers-first относится к реальному cohort; generic implementation не ждёт production facts. Одновременно legacy equality не оставлена скрытой authority лазейкой.

**Финальный delta redteam:** CAN и TC reviewers дали bounded GO документации. CAN reviewer потребовал привязать capacity bounds к реальному owner: дополнительное чтение Core подтвердило существующий `CoreJsonReadLimits`; решение теперь различает его lexical wire budget и logical `CanonSpec.max_depth`, требует explicit cohort policy и boundary/refusal probes до effects. TC reviewer потребовал проверять optional/non-null OpenAPI и nested presence в обоих snapshots/artifacts; T01/T03/T06 уточнены.

**Финальный самостоятельный проход G:** добавлены version-qualified reader policy для изменённых `.3` returns; повторная NL-law validation temporal artifact вместо пустого shared model; immutable resolution mutable branch selector; общий closure basis не включает identity output-report producer. Последнее сохраняет возможность сравнивать evidence разных owners, не ослабляя их отдельную provenance проверку.

## Источники и ограничения проверки

Входной `inputs-limits.json@757e407b` ссылается на полный bounded набор 13 TimeContext и 22 CAN current-source pins, а также 10 evidence entries. Они сверены без product execution. Primary source рассмотрен на `7a4c713`, включая дополнительные snapshot/scorecard/registry companions. Полный список дополнительных file hashes — [inputs.json](inputs.json); исходные arrays не скопированы второй раз.

Прочитаны original prototype-02/05 outputs и receipts. Prototype-02 — temporary CAS compatibility, без ordinary POST/producer authority. Prototype-05 — различие verified manifest views при совпадающем ID, принятое bare-ID comparison; вывод ограничен этой функцией. Historical CAN `state_projection_core_bytes_equal=true` — ошибочное имя поля: код probe вычисляет inequality, и показанные JSON projections различаются. Не выдавать это за равенство или новый runtime replay.

Source findings — static analysis, bounded historical evidence и проектные counterexamples. Предлагаемые grammar/types/schema versions ещё не реализованы. Нет новой native PASS, closure или production authority. Unknown input/backend/freeze gaps не стали “исправлены” от публикации документа.

## Pattern pass и правило завершения

P27/P31: изменяются текущие owners, class-wide structural invariants; P07: старые profiles/snapshots сохранены; P08: request/data/legal/publication не объединены; P05/P15: намерение/LLM не authority; P29/P32/P37/P38: реальный resolution и result effect вместо marker presence; P13: без registry/service proliferation; P40: residual объявлен по свойству, не по числу примеров; P41: непроверенная краснота не атрибутирована чужому owner.

Документарный completion: согласованные choices, wire/version/migration, полный named capability chain, реальные acceptance/removal signals, primary-source основания и explicit limitations. Кодовая acceptance остаётся за будущим independent review exact candidate и исполнением [матрицы](04-delivery-and-acceptance.md).
