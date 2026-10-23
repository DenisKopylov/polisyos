# E02: окончательные архитектурные ответы G — 23 октября 2026

Ответ на [пакет `f12fb9895a4009ce77828554f4c5c18d83e6ec15`](https://github.com/DenisKopylov/polisyos/blob/f12fb9895a4009ce77828554f4c5c18d83e6ec15/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/g-review-questions-20261023/README.md). **Решения выбраны для реализации; это не приёмка кода и не закрытие findings.** `code_acceptance=false`, `closure_ids=[]`. AD01–06, N818 и действующие system-design-decisions сохраняются. Новый global source/input/backend freeze не объявляется.

## Что выбрано

| Вопрос | Решение для исполнителя | Документ |
|---|---|---|
| IR-Q1: producer overrides и owner reader | Один механизм разрешения immutable owner contract для записи и типизированного чтения. Поддерживаемые представления объявляет владелец; сегодняшние defaults не образуют allowlist. Существующий generic JSON reader остаётся инструментом чтения байтов, а не доказательством типизированного допуска | [01 — контракт и реальные consumer escapes](01-ir-owner-contract.md) |
| IR-Q2: версии, история и миграция | Явно зарегистрированные представления и направленные правила совместимости; общий реестр, точные manifest/payload tuples, неизменная история. Reader-first rollout и проверяемый rollback. Публичная advisory-семантика ADR-0107 FULL сохраняется; типизированный intake использует строгий owner profile | [02 — совместимость](02-ir-version-compatibility.md) |
| PAG: вычисление при неизвестном юридическом основании | Разделить право обработать вход, условный математический вывод и право опереться на него в защищённом утверждении. Допустить полезную кандидатную математику над разрешёнными входами; сохранить legal refusal. Не создавать правовой факт из выбранной архитектуры | [03 — граница полномочий и времени](03-pag-scope-and-legal-relation.md) |
| R4: сохранённый conditional diagnostic | Явный request → существующий transport owner → отдельный кандидатный расчёт → CAS result/report → fresh consumer. Результат вложен в новый versioned diagnostic; внешний `UNSUPPORTED/NONE/false` не меняется. Никаких зеркал кандидатного score в старых полях confidence | [04 — контракт, wiring, migration и проверки](04-conditional-transport-diagnostic.md) |

Для PAG выбран **реальный ограниченный producer**, а не переименование старого sampler: конечное семейство проверенных no-selection MAG members, lossless ADMG representation, независимая проверка принадлежности исходному PAG и существующий solver по каждому допустимому member. Проект использует уже имеющийся optional causal-learn seam. Прямой scalar PAG/CPDAG gate сохраняется. Число успешных member-расчётов не является вероятностью, calibration или доказательством для всего класса. Подробный алгоритм, допущения, ограничения ресурсов и falsifiers — в [06](06-validated-partial-graph-profile.md).

## Расширяемость — отдельное условие готовности

«Один контракт» означает единый механизм интерпретации, а не один список разрешённых сегодня значений.

- Новый dataset, method instance или другой ресурс в уже принятой грамматике проходит существующий corpus/search/adapter путь **без правок central dispatch и без отдельной регистрации каждого ресурса в schema registry**.
- Новое wire-представление использует owner declaration, существующие validators и compatibility primitives. Повторяющиеся законы совместимости задаются один раз; матрицы и каталоги выводятся из них.
- Новая семантика требует собственного проверенного адаптера/правила. Артефакт не может выбрать себе исполняемый parser или issuer authority.
- Старые байты сохраняются. Неизвестная история остаётся доступной для разрешённого opaque inspection, но не получает выдуманной типизированной интерпретации.
- Приёмочные задания включают новый unseen resource, зарегистрированное nondefault representation, старый reader/new writer и rollback после публикации. Отказы без содержательного positive не считаются готовой capability.

## Как исполнять

Начать с [05 — очереди, ownership, настоящих внешних inputs и stop rules](05-implementation-and-inputs.md). Общий IR интерфейс и PAG/R4 дизайн могут разрабатываться параллельно; семейства IR разделяются по writers. На композиции требуются согласованные representation snapshots и обновлённые потребители. Не ждать полного production census или положительного юридического основания для независимых механизмов.

[callsite-disposition.json](callsite-disposition.json) распределяет все **93 строки / 53 caller paths** исходного CSV: 70 overrideable, 14 constant-only, 5 central, 2 known generic, 2 unresolved owner-law. Это остаточный смешанный source census, а не весь repository: 73 строки относятся к committed source, 8 — к dirty snapshot, 12 — к RAW postimages. Байты последних двух групп в этом review не подтверждены. При реализации нужен rebind на actual candidate, а не применение старых line numbers.

R4 наследует **33 seed paths** авторского пакета: 22 adoption, 3 documentation, 8 tests. Их exact pin проверен; это не верхний предел companions. И 93, и 33 — исходные множества маршрутизации, не критерий завершения всей работы. [inputs.json](inputs.json) фиксирует источник, hashes, знаменатели и пределы выполненной проверки.

## Основания выбора и проверка проекта

[07 — первичные источники и tradeoffs](07-research-and-tradeoffs.md) сопоставляет практики Avro, Iceberg, Protobuf, Confluent, JSON Schema, TUF и исследования partial-graph causal inference с существующими owners PolicyOS. Мы заимствуем применимые механизмы, не добавляем эти платформы целиком.

[08 — red-team, исправления и самостоятельное review G](08-review-and-final-disposition.md) показывает найденные слабости, их устранение и сохранённые ограничения. Runtime acceptance остаётся задачей исполнителя и последующей G-приёмки. Документационные проверки не заменяют actual producer → artifact → bridge → consumer → semantic test.

Подлинные law/issuer/custody/currentness/calibration факты и утраченные исторические источники не возникают из этого коммита. Исполнитель должен сначала проверить, может ли завершить соответствующий programming contract или восстановить факт из существующих источников, а затем назвать точный оставшийся внешний input. Повторное общее «нужно решение G» по четырём выбранным вопросам не требуется; новый конкретный научный или authority-конфликт оформляется отдельно.
