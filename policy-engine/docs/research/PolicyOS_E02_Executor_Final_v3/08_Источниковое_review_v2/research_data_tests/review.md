# Исследование: эволюция данных и сила тестового доказательства

Дата чтения источников: **1 ноября 2026 UTC**. Фаза: **только research**, до проверки текущих 127 пакетов и 12 лейнов. Прочитаны релевантные разделы 20 первичных официальных/авторских источников; выведены **11 условно применимых критериев**. Ни одного дефекта E02 здесь не заявлено.

## Главное для следующего прохода

- Decode/schema-valid не означает сохранение смысла при mixed-version handoff. Проверяется поддерживаемая направленная пара writer→reader и значимый промежуточный путь, а не произвольные исторические версии. [AIP-180](https://google.aip.dev/180), [Protobuf evolution](https://protobuf.dev/programming-guides/proto3/#updating).
- Deterministic output не равен stable semantic identity; replay не равен независимой правильности. Эти доказательства полезны, но отвечают на разные вопросы. [Protobuf canonicalization limits](https://protobuf.dev/programming-guides/serialization-not-canonical/), [NASEM, глава 4, с.59, прим.3](https://www.nationalacademies.org/read/25303/chapter/7).
- Тестовые подходы не превращаются в обязательный список технологий. Ищется **минимальное различающее свидетельство**: ошибочная, но допустимая по предусловиям реализация должна не пройти именно проверяемое обещание. Число тестов, один hash, общий oracle или mutation score сами по себе недостаточны.
- Не подменять schema assertions аннотациями. В частности, JSON Schema 2020-12 format-annotation не требует обычного format rejection, default не материализует поле. [Validation §§7.2,9.2](https://json-schema.org/draft/2020-12/json-schema-validation), [официальное пояснение default](https://json-schema.org/understanding-json-schema/reference/annotations).

## Границы и способ применения

1. Сначала найти в конкретном ТЗ обещание и trigger критерия. Без trigger — not-applicable с причиной, а не обязательное расширение ТЗ.
2. Проверить полный локальный и общий контракт, существующие shared bindings/limits. Если описанная плохая реализация уже исключена другим обязательным TEST/REQ, нового finding нет.
3. Различать **качество спецификации испытания** и **фактическое выполнение**. Covered означает, что ТЗ предусматривает достаточную проверку, не что продукт прошёл её. Research не требует запускать тесты или внедрять библиотеки.
4. Конкретные контрпримеры ниже — наши мысленные инженерные примеры, а не результаты E02 и не цитаты источников. Исправление формулировки выбирается минимальным и совместимым с существующим scope.
5. Стандарты форматов обязательны лишь для принятого профиля; AIP/Google practices/NASEM/Hypothesis — источники аргументации, а не универсальный закон архитектуры. Допускаются альтернативные механизмы с той же различающей силой.

## Каталог критериев

### DAT-01. Совместимость — направленный контракт по всему маршруту, а не успешный decode

**Когда применим.** Есть обещание совместимости версий, обновление схемы/API, сохранённые записи, раздельно обновляемые producer/consumer, конвертер или forwarding между лейнами.

**Что подтверждено источниками.** Первичные источники различают source/wire/semantic compatibility, условно безопасные изменения и writer/reader resolution. Успешное чтение не исключает потери значения или полей. [DAT-S01: AIP-180: Backwards compatibility](https://google.aip.dev/180); [DAT-S02: Language Guide (proto3)](https://protobuf.dev/programming-guides/proto3/); [DAT-S05: Apache Avro 1.12.0 Specification](https://avro.apache.org/docs/1.12.0/specification/).

**Corner case.** Новый writer выдаёт int64 выше диапазона старого int32; старый consumer успешно разбирает, но усекает значение. В другом маршруте новое поле переживает binary decode старым relay, затем теряется при его proto→JSON→proto. В Avro новое обязательное reader-поле без default ломает чтение старой записи.

**Плохое ТЗ / слабый тест, который может пройти.** «Изменения additive и backward-compatible; старые и новые сообщения декодируются». Тест использует только latest→latest либо маленькое положительное число и не проверяет фактический смысл результата. Положительные локальные тесты endpoints не покрывают старый relay.

**Исправленное ожидание к контракту.** Назвать поддерживаемые версии, направление compatibility, представление и семантические инварианты; описать handling unknown fields/enum variants и ограничение записи новых значений в rollout. Для backward/forward не полагаться на неодинаковое толкование терминов: явно указать writer→reader.

**Различающее доказательство:**
- Матрица old writer→new reader и new writer→old reader в обещанном окне; unsupported pairs явно отклоняются или не заявлены.
- Boundary fixture, различающий успешный parse и сохранение значения; отсутствующее поле, новый enum/union variant только где они применимы.
- Если маршрут сохраняет/трансформирует/пересылает данные: новый writer→реальный старый посредник→новый consumer с проверкой требуемого конечного состояния; persisted old record и rollback — только если это часть обещания.
- В ТЗ достаточно точно заданного испытания и oracle; заявление «испытано» дополнительно требует версии, fixture и результатов, а не только схемы.

**Ограничения:**
- Не все исторические версии и не все транспорты: только объявленное окно и существующие пути.
- Protobuf/Avro-specific детали неприменимы без соответствующего формата; общая проблема совместимости остаётся условной.
- Отказ от forward compatibility допустим, если согласован с реальным rollout и не противоречит общему контракту.

**Компромисс.** Терпимое чтение улучшает эволюцию, но может скрыть потерю значимых данных; strict rejection безопаснее для некоторых полей, но ограничивает rolling update. Выбор должен быть явным, не универсальным.

**Межлейновый стык.** Сопоставить producer version, encoding, adapter policy и consumer version одной передачи; два независимых PASS по разным fixtures не образуют общий compatibility witness.

**Статус вывода.** Матрица и конкретные discriminators — наша ограниченная инженерная операционализация источников; это не найденный дефект E02.

### DAT-02. Absent, explicit default, null и unknown — разные состояния, пока контракт не определил обратное

**Когда применим.** Есть partial update/merge, необязательные поля, reset/clear, defaults, конфигурация или пересечение сериализаторов с разной presence-семантикой.

**Что подтверждено источниками.** Implicit protobuf merge не передаёт установку в default; JSON Schema default не материализует поле; Avro default действует при чтении отсутствующего writer-поля, а не делает запись необязательной. [DAT-S03: Application Note: Field Presence](https://protobuf.dev/programming-guides/field_presence/); [DAT-S05: Apache Avro 1.12.0 Specification](https://avro.apache.org/docs/1.12.0/specification/); [DAT-S08: JSON Schema Validation: A Vocabulary for Structural Validation of JSON](https://json-schema.org/draft/2020-12/json-schema-validation); [DAT-S10: Understanding JSON Schema: Annotations](https://json-schema.org/understanding-json-schema/reference/annotations).

**Corner case.** У объекта limit=10; patch с explicit 0 должен выключить лимит, но merge пропускает 0. Валидатор принимает объект без limit, однако runtime не подставляет обещанный default. JSON null интерпретируется одним лейном как clear, другим — как отсутствие и preserve.

**Плохое ТЗ / слабый тест, который может пройти.** «Пустые значения используют default; patch сохраняет остальные поля». Тест проверяет только update 10→20 и round trip непустого сообщения. Он не различает отсутствие, ноль, false, пустую строку и явный null.

**Исправленное ожидание к контракту.** Для каждого семантически значимого optional/update-поля дать таблицу состояний на границе: отсутствует / explicit default / null (если допустим) / иное значение; определить preserve/set/clear/reject и владельца default-materialization. Unknown-field policy не смешивать с null.

**Различающее доказательство:**
- Fixtures со старым non-default состоянием и отдельными отсутствующим, default-valued и null patch; проверять конечное состояние и сообщения об отказе, где требуется.
- Ожидания по initial create и update разделены; default из schema annotation не считается автоматически исполняемым.
- При mixed presence пройти полный encode→adapter→decode→merge путь; проверять значение и наличие отдельно, когда наличие значимо.

**Ограничения:**
- Не требуется различать состояния, если контракт явно считает их эквивалентными и это безопасно для потребителей.
- Не требовать nullable всех типов или optional всех protobuf-полей.
- Пустой список/строка — отдельный кейс только при семантической значимости, а не механически для каждого поля.

**Компромисс.** Более богатая presence-семантика повышает выразительность и сложность клиентов. Возможны explicit presence, field mask или отдельная clear-операция; критерий не выбирает за проект.

**Межлейновый стык.** Проверить, что источник default, схема envelope, adapter и владелец patch применяют одну таблицу состояний.

**Статус вывода.** Таблица состояний — наша форма проверки; источники обосновывают необходимость не смешивать эти понятия.

### DAT-03. Byte identity, canonical representation и семантическая идентичность не взаимозаменяемы

**Когда применим.** Хеш, cache key, deduplication, подпись, evidence ID, сравнение результатов или replay заявлены как свидетельство равенства сущностей, а не просто целостности конкретного файла.

**Что подтверждено источниками.** Protobuf deterministic serialization не канонична между версиями/сборками. JCS задаёт ограниченный канонический JSON, но не Unicode normalization и не прикладную эквивалентность. [DAT-S04: Proto Serialization Is Not Canonical](https://protobuf.dev/programming-guides/serialization-not-canonical/); [DAT-S06: RFC 8785: JSON Canonicalization Scheme (JCS)](https://www.rfc-editor.org/rfc/rfc8785.html); [DAT-S07: RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html).

**Corner case.** Одинаковый объект с иным порядком JSON-полей получает иной raw hash; два разных integer IDs выше точной float-границы сливаются после преобразования; массив, где порядок значим, ошибочно сортируется как множество. Смена protobuf runtime меняет bytes при прежнем смысле.

**Плохое ТЗ / слабый тест, который может пройти.** «Использовать детерминированную сериализацию и SHA-256 для стабильного semantic_id». Тест хеширует один объект дважды тем же binary; либо проверяет только idempotence canonicalizer, которую удовлетворяет и константная функция.

**Исправленное ожидание к контракту.** Назвать вид идентичности и область стабильности. Для semantic identity определить входящие поля, контекст/версии, эквивалентности и неоднозначные/неподдерживаемые входы. Для wire signature определить точные bytes/profile. Канонизация представления и нормализация смысла — разные стадии.

**Различающее доказательство:**
- Пары семантически равных представлений и пары обязательно различных сущностей; equality-only тест недостаточен.
- Если выбран JCS: соответствие выбранному профилю, duplicates и невалидный Unicode отклоняются; array order сохраняется; числовая точность явно ограничена/представлена.
- Проверить только обещанные реализации/версии; для миграции identity namespace/version или иной согласованный переход.
- Тест должен различать потерю данных от допустимого изменения представления, а не требовать произвольного bitwise equality.

**Ограничения:**
- Raw bytes hash корректен для integrity одного неизменного артефакта; этот критерий не объявляет его ошибкой.
- Не навязывать JCS, Unicode normalization, второй хеш или поддержку всех числовых типов.
- Отсутствующие unknown fields не нужно искусственно изобретать, если область гарантированно закрыта и эта граница защищена контрактом.

**Компромисс.** Широкая semantic equivalence повышает риск коллизий смысла; слишком узкая byte equality даёт ложные различия. Выбор зависит от назначения ключа.

**Межлейновый стык.** Совпадают ли проекция полей, порядок/точность, namespace и версия identity у producer и каждого потребителя?

**Статус вывода.** Пары equal/unequal и запрет смешивать виды идентичности — наш вывод из явных ограничений сериализаций.

### DAT-04. Схема проверяет только реально поддерживаемый dialect и активные assertions

**Когда применим.** Приёмка ссылается на JSON Schema/OpenAPI schema, custom keywords/formats, allOf/$ref composition или обещает расширяемый, но закрытый envelope.

**Что подтверждено источниками.** JSON Schema различает annotations и assertions; $schema/$vocabulary задают dialect. Unknown keyword может не проверяться. additionalProperties ограничено тем же schema object; format-annotation не гарантирует semantic validation. [DAT-S08: JSON Schema Validation: A Vocabulary for Structural Validation of JSON](https://json-schema.org/draft/2020-12/json-schema-validation); [DAT-S09: JSON Schema: A Media Type for Describing JSON Documents](https://json-schema.org/draft/2020-12/json-schema-core).

**Corner case.** Поле timestamp содержит format:date-time, но выбранный validator трактует format лишь как annotation. Опечатка в custom keyword даёт ложный PASS. allOf добавляет поле к base schema с additionalProperties:false, и корректное расширение становится невалидным.

**Плохое ТЗ / слабый тест, который может пройти.** «Вход валиден по JSON Schema, следовательно все форматы и бизнес-ограничения соблюдены». Тест проверяет meta-schema или валидный happy path, но не заведомо запрещённый instance.

**Исправленное ожидание к контракту.** Зафиксировать dialect/version, vocabulary и важные validator options. Разделить проверку самой схемы, instance validation, format syntax и прикладную семантику. Для композиции указать допустимые extensions и unknown-field policy.

**Различающее доказательство:**
- Для реально значимых ограничений по одному запрещённому discriminator: неверный format, неизвестное/неподдержанное требование, закрытое/допустимое extension-поле.
- Тестировать final composed/bundled schema в фактическом режиме валидатора, не только каждый фрагмент по отдельности.
- Для custom vocabulary определить fail/refuse/support behavior; документировать ограничения format-checker, не выдавать синтаксическую проверку за существование URL/email.

**Ограничения:**
- Только используемый dialect; OpenAPI 3.0 и 3.1 нельзя без проверки считать JSON Schema 2020-12.
- Не требуется запрещать все дополнительные поля или всегда включать все formats.
- Не требуется сетевое разрешение каждого $ref; достаточно однозначно определённого набора schema resources.

**Компромисс.** Закрытые схемы ловят опечатки, но усложняют эволюцию; tolerant schemas удобнее для расширений. Ужесточение должно учитывать DAT-01, а не автоматически становиться исправлением.

**Межлейновый стык.** Одинаково ли трактуются общий envelope и дополнительные поля после composition у validator, adapter и consumer?

**Статус вывода.** Discriminator fixtures — наша рекомендация проверить реально обещанную семантику, а не расширить стандарт.

### DAT-05. Повторяемость и независимость oracle — разные оси доказательства

**Когда применим.** Есть утверждения «воспроизводимо», «независимо подтверждено», golden/reference output, сравнение двух реализаций, несколько verdicts или общий verifier в разных лейнах.

**Что подтверждено источниками.** NASEM прямо отделяет воспроизводимость от правильности; Google показывает общий дефект production/expected logic и рекомендует наблюдать контрактное поведение. [DAT-S11: Reproducibility and Replicability in Science — Chapter 4: Reproducibility](https://www.nationalacademies.org/read/25303/chapter/7); [DAT-S12: Software Engineering at Google — Chapter 12: Unit Testing](https://abseil.io/resources/swe-book/html/ch12.html).

**Corner case.** Production и oracle используют один и тот же ошибочный normalizer или comparator. Они стабильно возвращают одинаковый результат на одном dataset, и второй runner только повторяет вызов. Hash, два лога и replay подтверждают устойчивость этой ошибки, а не истинность результата.

**Плохое ТЗ / слабый тест, который может пройти.** «Повторить трижды, hashes совпадают — correctness подтверждена независимо». Или expected генерируется тем же production function, а отдельный процесс считается независимым oracle.

**Исправленное ожидание к контракту.** Раздельно задать replay claim (что повторяется, при каких входах/версиях/окружении/допусках) и correctness oracle (откуда ожидаемый смысл, что независимо от изменяемого пути). Зафиксировать допустимые общие зависимости и ограничения независимости.

**Различающее доказательство:**
- Provenance manifest входов, code/schema/data versions, параметров и relevant environment для replay.
- Для критичного утверждения — проверяемый вручную discriminating fixture, проще устроенная reference model, внешний нормативный expected либо другой обоснованный источник истины; не обязательно всё сразу.
- Объяснить dependency overlap SUT/oracle, включая генератор expected и нормализатор; изменение проверяемой ошибки должно менять verdict.
- Наблюдать обещанный результат/состояние на контрактной границе; внутренний флаг success не заменяет результат handoff.

**Ограничения:**
- Повторный запуск полезен и не обесценивается; просто его нельзя выдавать за независимую correctness-проверку.
- Не требуются разные организации, языки или ОС для каждого теста; независимость определяется по существенному риску.
- Общий parser не всегда порок: допустим, если parser correctness не объект данного утверждения и это явно ограничено.

**Компромисс.** Полностью независимый oracle дорог и иногда невозможен. Bounded independence + простые anchors/negative controls честнее, чем необоснованная абсолютная независимость.

**Межлейновый стык.** Не считать один shared oracle/fixture несколькими независимыми подтверждениями; tracing должен показывать реальное происхождение и свежего consumer.

**Статус вывода.** Разделение replay/correctness и dependency-overlap review — наша операционализация; источники не требуют полной независимости всего стека.

### DAT-06. Property-based test проверяет сформулированное свойство на заявленном домене, не полноту системы

**Когда применим.** ТЗ использует generative/property/fuzz testing, много случайных примеров, фиксированные seeds или обещает широкое покрытие входного пространства.

**Что подтверждено источниками.** Hypothesis предупреждает о потере bug-triggering inputs при чрезмерном сужении домена и об инвалидируемой replay database. [DAT-S13: Hypothesis: Domain and distribution](https://hypothesis.readthedocs.io/en/latest/explanation/domain.html); [DAT-S14: Hypothesis: Replaying failed tests](https://hypothesis.readthedocs.io/en/latest/tutorial/replaying-failures.html).

**Corner case.** Генератор создаёт только непустые уникальные списки, хотя функция обязана сохранять duplicates. Проверка «выход отсортирован и set(input)=set(output)» пропускает ошибочный deduplicating sort. В другом случае assume отбрасывает все значимые boundary cases.

**Плохое ТЗ / слабый тест, который может пройти.** «10 000 случайных тестов прошли, значит все corner cases закрыты». Нет определения домена, исключений и свойства; seed записан без версии генератора, а найденный сбой остаётся только в локальном кэше.

**Исправленное ожидание к контракту.** Определить property, допустимый домен/границы/исключения и какие классы ошибок оно различает. Нужные граничные случаи закрепить явно; найденный контрпример сохранить как regression input/trace с контекстом.

**Различающее доказательство:**
- Описание generator constraints и причины исключений; count принятых/отброшенных случаев или иной способ увидеть пустую проверку, когда это риск.
- Небольшой known-bad discriminator: например потеря повторов при сортировке должна проваливать полный контракт свойства.
- Сохраняемый конкретный минимизированный failing input/trace; seed дополнительно, а не как универсальная переносимость.
- Отдельные обязательные boundary fixtures там, где случайный поиск не даёт гарантии посещения.

**Ограничения:**
- Не требовать безграничного генератора; performance/resource limits допустимы и должны ограничивать силу вывода.
- Не требовать конкретный framework, число примеров или probabilistic guarantee без обоснования.
- PBT не заменяет тест взаимодействия лейнов или независимый expected для всех свойств.

**Компромисс.** Широкий домен полезен, но может быть дорог; разумны bounded partitions и отдельные stress cases. Пустые/тривиальные свойства не исправляются простым увеличением числа запусков.

**Межлейновый стык.** Один и тот же admissible domain должен быть принят downstream; локальный generator не должен исключать допустимые upstream payloads.

**Статус вывода.** Пример deduplicating sort и non-vacuity discriminator — наши мысленные контрпримеры, не дефекты документации Hypothesis и не результат запуска продукта.

### DAT-07. Metamorphic relation требует обоснованных предпосылок и не заменяет все ожидаемые результаты

**Когда применим.** Есть сложный oracle, обещания инвариантности/монотонности/идемпотентности, reorder/rename/rescale transformations или metamorphic tests.

**Что подтверждено источниками.** Metamorphic testing связывает несколько входов/выходов; генерация и shrinking обязаны сохранять условия отношения. [DAT-S16: Application of property-based testing tools for metamorphic testing](https://arxiv.org/pdf/2211.12003); [DAT-S13: Hypothesis: Domain and distribution](https://hypothesis.readthedocs.io/en/latest/explanation/domain.html).

**Corner case.** Заявлена инвариантность результата при перестановке evidence, но порядок фактически имеет приоритетный смысл; такой тест ложно обвинит корректную реализацию. Обратная ошибка: relation f(f(x))=f(x) принимает константную функцию и не доказывает полезную нормализацию.

**Плохое ТЗ / слабый тест, который может пройти.** «Все преобразования входа сохраняют результат; проверить несколько permutations». Не задано, что сохраняется: bytes, множество, порядок, величина с допуском; не указаны предусловия и forbidden transformations.

**Исправленное ожидание к контракту.** Для выбранного relation записать исходный домен, преобразование T, предпосылки P и ожидаемую связь R(outputs), включая нужный tolerance. Различать необходимое свойство и полную спецификацию. Сохранять предусловия при shrinking.

**Различающее доказательство:**
- Нетривиальная пара source/follow-up inputs, для которой T действительно допустимо; отдельно пример вне предусловия, который не используется как обвиняющий oracle.
- Хоть один anchor или другой relation, исключающий очевидный degenerate implementation (constant/identity/drop-all) для данного требования.
- Контрпример хранит обе связанные входные формы и результаты; shrinking не разрушает сам relation.
- Проверить, что relation выведен из предметного контракта, а не из текущего поведения SUT.

**Ограничения:**
- Не навязывать metamorphic testing там, где простые known expected outputs достаточны.
- Не требовать invariance для порядка/масштаба/имен автоматически: это предметные решения.
- Relation, найденный эмпирически, сначала гипотеза; он не нормативен без согласования.

**Компромисс.** Metamorphic tests полезны при дорогом oracle, но могут пропускать согласованно неверные результаты или ложно падать при невалидной трансформации.

**Межлейновый стык.** Transformation должна сохранять сквозные предпосылки: id/context/version/order у всех участвующих лейнов, а не только local input schema.

**Статус вывода.** Формальная форма P/T/R и degenerate examples — наша ограниченная проверочная интерпретация первичной работы.

### DAT-08. Истории переходов проверяются отдельно от изолированных операций

**Когда применим.** Есть lifecycle, create/update/delete, cache/invalidation, replay/reset, миграция или операции, результат которых зависит от предыдущих действий.

**Что подтверждено источниками.** Stateful testing генерирует цепочки действий и сверяет их с упрощённой моделью; для простых случаев state machine не обязательна. [DAT-S15: Hypothesis: Stateful tests](https://hypothesis.readthedocs.io/en/latest/stateful.html); [DAT-S12: Software Engineering at Google — Chapter 12: Unit Testing](https://abseil.io/resources/swe-book/html/ch12.html).

**Corner case.** Create и delete проходят по отдельности, но delete→recreate оставляет устаревшую запись cache. Либо rollback после частичного update восстанавливает значение, но не presence/version. Модель, которая вызывает тот же production transition helper, повторяет дефект.

**Плохое ТЗ / слабый тест, который может пройти.** «Все операции покрыты unit-тестами». Для каждой операции создаётся свежее состояние; история, допустимые переходы и наблюдаемый state не специфицированы.

**Исправленное ожидание к контракту.** Описать минимальные значимые состояния/переходы, предусловия и postconditions/invariants, порядок наблюдений и что сохраняется после ошибки. Reference model должна быть проще и независима в проверяемом аспекте.

**Различающее доказательство:**
- Короткая последовательность, отличающая корректный lifecycle от stale-state реализации: напр. create→update→delete→recreate→read, только если такая история допустима.
- Наблюдение after-step invariant и конечного состояния, а не только количества успешных API-ответов.
- Illegal transition имеет предусмотренный reject/no-op outcome и не повреждает состояние, если это обещано.
- Сохраняемый action trace и initial state для воспроизведения; связи с реальным handoff на уровне интеграции.

**Ограничения:**
- Не требует отдельного FSM для stateless helper.
- Последовательная модель не доказывает параллельность, atomicity, crash recovery или linearizability; эти утверждения требуют своей модели/испытания.
- Не включать запрещённые lifecycle истории как обязательный supported path.

**Компромисс.** Полная модель быстро усложняется и рискует стать второй реализацией. Лучше bounded модель критичных инвариантов плюс named exclusions.

**Межлейновый стык.** Сквозной state owner и момент наблюдения должны совпадать; локальные состояния разных лейнов не равны глобальному завершению.

**Статус вывода.** Сценарии cache/lifecycle — наши примеры применения stateful подхода, не предположение о наличии таких дефектов в E02.

### DAT-09. Mutation/negative-control доказательство должно показывать, какую ошибку и каким assertion оно обнаруживает

**Когда применим.** ТЗ ссылается на coverage/mutation score/negative controls либо приёмочный oracle выглядит способным принимать заведомо неверный результат.

**Что подтверждено источниками.** Состояния mutant и знаменатель score различаются; timeout не semantic assertion failure, а equivalent mutant не может быть убит корректным тестом. [DAT-S17: Stryker: Mutant states and metrics](https://stryker-mutator.io/docs/mutation-testing-elements/mutant-states-and-metrics/); [DAT-S18: StrykerJS: Disable mutants](https://stryker-mutator.io/docs/stryker-js/disable-mutants/).

**Corner case.** Система объявляет 100% mutation score: большая часть изменений вызвала timeouts, а значимые mutants оказались ignored/compile errors. Или единственный negative test ломает JSON-синтаксис и не доказывает обнаружение неверного, но schema-valid решения.

**Плохое ТЗ / слабый тест, который может пройти.** «Mutation score ≥ X, значит contract доказан». Не указаны mutation operators, область, исключения, outcomes и связь с реальной ошибкой. Любая авария runner считается обнаружением семантического нарушения.

**Исправленное ожидание к контракту.** Описать несколько релевантных fault models и наблюдаемую причину rejection/failure. Если используется агрегат, зафиксировать numerator/denominator/status accounting и причины исключений.

**Различающее доказательство:**
- Representative mutant или handcrafted negative control, сохраняющий входные предусловия, но нарушающий проверяемое обещание, должен провалить нужный assertion.
- Разделить killed, timeout, survived, no-coverage, ignored, invalid и pending согласно выбранному инструменту.
- Survivor triage: эквивалентность / вне области / неубедительный тест / неизвестно; не считать эквивалентность доказанной без объяснения.
- Не ограничиваться malformed-input control для semantic property; полезен schema-valid wrong value/order/owner/version.

**Ограничения:**
- Не обязательный полный mutation run каждого пакета и не требование 100%.
- Для простого теста достаточно одного ясного negative discriminator; native mutation services в этой работе не запускаются.
- Timeout может быть допустимым detector для liveness, но не подменяет доказательство иной property.

**Компромисс.** Mutation testing дорого и зависит от operators; небольшой набор осмысленных controls иногда сильнее большого процента нерелевантных мутантов.

**Межлейновый стык.** Fault injection/negative fixture должно попадать в реально проверяемую границу, не лишь ломать общий harness до handoff.

**Статус вывода.** Требование semantic negative controls и mapping к assertions — наше применение определений инструментов.

### DAT-10. Оценочный набор не должен участвовать в выборе оцениваемого решения без явного ограничения вывода

**Когда применим.** Есть обучение, калибровка score/threshold, retrieval/ranking quality, сравнение методов на dataset или заявление о переносимости на невиданные данные.

**Что подтверждено источниками.** Обучение preprocessing/выбор модели по test data приводит к optimistic estimates; воспроизводимость такого процесса не исправляет leakage. [DAT-S19: scikit-learn: Common pitfalls and recommended practices](https://scikit-learn.org/stable/common_pitfalls.html); [DAT-S11: Reproducibility and Replicability in Science — Chapter 4: Reproducibility](https://www.nationalacademies.org/read/25303/chapter/7).

**Corner case.** Normalizer или feature selector обучен на общем наборе до split; threshold выбран по final evaluation labels. В лейн-пайплайне test outcome возвращается в builder, после чего тот же набор снова предъявляется как независимая проверка.

**Плохое ТЗ / слабый тест, который может пройти.** «Train и test файлы разные, accuracy ≥ X; seed фиксирован». При этом preprocessing использует оба файла либо качество многократно подгоняется по test. Для non-ML контракта ошибка-аналог: expected fixtures созданы из проверяемого результата и названы независимым benchmark.

**Исправленное ожидание к контракту.** Назвать роли data: development/calibration/evaluation, что может быть известно при построении решения, где выполняется fit/tune и какая версия решения заморожена до итоговой оценки. При повторном использовании набора ограничить claim.

**Различающее доказательство:**
- Lineage split и transforms: параметры обучены на допустимой части; eval используется для transform/score, не для fit/tune.
- Для связанных сущностей/времени — правило разделения, соответствующее заявленной generalization, если такие зависимости входят в задачу.
- Сохранить конфигурацию до финальной оценки и журнал выбора threshold/model; не требовать секретности обычных regression tests.
- Показывать denominator, exclusions и ошибки отдельно от выбранных успешных примеров; не выдавать tuned benchmark за независимое обобщение.

**Ограничения:**
- Вне ML перенос на threshold/ranking — наша аналогия, применимая лишь при заявлении объективной внешней оценки.
- Обычные deterministic regression fixtures разрешено видеть разработчику; это не leakage само по себе.
- Не требовать новых private datasets или установленного sample size без предметного основания.

**Компромисс.** Holdout расходует данные; повторное использование допустимо для разработки при честной маркировке. Нельзя автоматически отменять весь результат, если claim ограничен in-sample regression.

**Межлейновый стык.** Проверить обратные связи: не получает ли producer/selector сведения из оценочного consumer до freeze, в том числе через shared defaults, normalization или labels.

**Статус вывода.** Generalization split по entity/time и non-ML аналогии — условное применение, не универсальная норма scikit-learn.

### DAT-11. Benchmark должен измерять заявленный результат в заявленных условиях

**Когда применим.** Есть latency/throughput/resource claims, улучшение относительно baseline, fast path или оценка эффективности алгоритма.

**Что подтверждено источниками.** Benchmark зависит от вида таймера, прогрева, повторений и оптимизации измеряемой работы. Перезапускаемый microbenchmark не равен end-to-end latency или доказательству product capability. [DAT-S20: Google Benchmark User Guide](https://google.github.io/benchmark/user_guide.html); [DAT-S11: Reproducibility and Replicability in Science — Chapter 4: Reproducibility](https://www.nationalacademies.org/read/25303/chapter/7).

**Corner case.** Замеряет только постановку асинхронной задачи, а не завершение; CPU timer не учитывает работу других threads. Компилятор устраняет постоянное вычисление. Среднее нескольких repetition means выдаётся за p99 пользовательских запросов; cold start исключён, хотя SLO его включает.

**Плохое ТЗ / слабый тест, который может пройти.** «Benchmark прошёл; ускорение 2×». Нет workload/versions/clock/границы start-stop; сравниваются разные нагрузки либо dry run с одной итерацией.

**Исправленное ожидание к контракту.** Назвать unit of work, correctness condition, clock/timing boundary, workload и state (cold/warm), concurrency, baseline, hardware/software context и способ агрегирования. Claim должен оставаться в пределах реально измеренного.

**Различающее доказательство:**
- Проверить выполнение/завершение полезной работы и сохранение correctness; отсутствие work elimination или cache-hit-only подмены, если это значимо.
- Сопоставимые baseline/candidate условия, raw observations/repetitions и выбранная статистика с объяснением вариабельности.
- Если заявлен percentile/SLO — наблюдения соответствующих операций, а не percentile из несопоставимых средних; exact threshold не изобретать.
- Manifest достаточен для повторения; явные исключения setup/network/cold start не должны противоречить названию claim.

**Ограничения:**
- Не требовать универсальное число повторов, warmup или SLO; они зависят от property и среды.
- Microbenchmark допустим для локальной стоимости; не объявлять его плохим только потому, что он не E2E.
- Нельзя запускать native services/benchmarks в данной research-фазе; речь о требованиях к доказательству.

**Компромисс.** Изоляция снижает шум, но уменьшает реализм; end-to-end измерение реалистичнее, но хуже локализует причину. Обе формы полезны при раздельных claims.

**Межлейновый стык.** Убедиться, что начало/конец сквозной операции и workload одни и те же для producer, handoff и consumer; суммы локальных средних не равны автоматически latency распределению всей цепочки.

**Статус вывода.** Условия сопоставимости и запрет подмены статистик — наши ограниченные выводы из измерительных гарантий, не готовый SLO для E02.

## Источники: версии и локаторы

Полные записи и ограничения доступа находятся в `sources.json`. URL /latest и /stable — изменяемые страницы, не pin версии runtime E02. Номера версий ниже — то, что показал сайт при чтении. Заголовок AIP-180 показывает старую дату updated, тогда как changelog включает 2025-10-21; это явно сохранено, а не принято за неизменность с 2019 года.

- **DAT-S01** — [AIP-180: Backwards compatibility](https://google.aip.dev/180). AIP-180; Approved; header created/updated 2019-07-23, но changelog содержит изменение 2025-10-21; live page accessed 2026-11-01. Локаторы: Guidance (source / wire / semantic compatibility); Adding components; Semantic changes. Тип: Рекомендация владельца API, не универсальный стандарт.
- **DAT-S02** — [Language Guide (proto3)](https://protobuf.dev/programming-guides/proto3/). proto3; live documentation; точная версия runtime не заявлена. Локаторы: Updating A Message Type → Binary Wire-safe Changes; Binary Wire-compatible Changes (Conditionally Safe); Unknown Fields → Retaining Unknown Fields; Backwards-compatibility issues (oneof). Тип: Официальная документация формата.
- **DAT-S03** — [Application Note: Field Presence](https://protobuf.dev/programming-guides/field_presence/). Live application note; proto2/proto3/editions distinctions. Локаторы: Considerations for Merging; Considerations for change-compatibility. Тип: Официальное описание семантики presence.
- **DAT-S04** — [Proto Serialization Is Not Canonical](https://protobuf.dev/programming-guides/serialization-not-canonical/). Live documentation. Локаторы: Implications on Fingerprinting and Cryptographic Hashing; Deterministic is not Canonical. Тип: Официальная гарантия/ограничение сериализации.
- **DAT-S05** — [Apache Avro 1.12.0 Specification](https://avro.apache.org/docs/1.12.0/specification/). 1.12.0. Локаторы: Complex Types → Records (default); Schema Resolution; Parsing Canonical Form for Schemas. Тип: Спецификация формата.
- **DAT-S06** — [RFC 8785: JSON Canonicalization Scheme (JCS)](https://www.rfc-editor.org/rfc/rfc8785.html). RFC 8785, June 2020, Informational / Independent Submission. Локаторы: §3.1 Creation of Input Data; §3.2.2.2 Serialization of Strings; §3.2.2.3 Serialization of Numbers; §3.2.3 Sorting of Object Properties. Тип: Спецификация JCS; не Internet Standards Track.
- **DAT-S07** — [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html). RFC 8259, December 2017; Standards Track. Локаторы: §4 Objects; §6 Numbers; §8.2 Unicode Characters; §8.3 String Comparison; §9 Parsers. Тип: Стандарт JSON.
- **DAT-S08** — [JSON Schema Validation: A Vocabulary for Structural Validation of JSON](https://json-schema.org/draft/2020-12/json-schema-validation). Draft 2020-12; draft-bhutton-json-schema-validation-01, 2022-06-16; Internet-Draft/work in progress, не RFC. Локаторы: §6.5.3 required; §7.2.1 Format-Annotation Vocabulary; §7.2.2 Format-Assertion Vocabulary; §9.2 default. Тип: Версионированная опубликованная спецификация JSON Schema vocabulary.
- **DAT-S09** — [JSON Schema: A Media Type for Describing JSON Documents](https://json-schema.org/draft/2020-12/json-schema-core). Draft 2020-12; draft-bhutton-json-schema-01, 2022-06-16; Internet-Draft/work in progress, не RFC. Локаторы: §4.3.1 Schema Objects and Keywords; §8.1.1 The $schema Keyword; §8.1.2 The $vocabulary Keyword; §9.3 Compound Documents; §10.3.2.3 additionalProperties. Тип: Версионированная опубликованная спецификация core.
- **DAT-S10** — [Understanding JSON Schema: Annotations](https://json-schema.org/understanding-json-schema/reference/annotations). Live official explanatory guide. Локаторы: Annotations → default. Тип: Официальное пояснение, не отдельная normative specification.
- **DAT-S11** — [Reproducibility and Replicability in Science — Chapter 4: Reproducibility](https://www.nationalacademies.org/read/25303/chapter/7). 2019; DOI 10.17226/25303. Локаторы: Recommendation 4-1, pp.58–59; Assessing Reproducibility, p.59; Footnote 3, p.59. Тип: Консенсусный исследовательский отчёт; не software conformance standard.
- **DAT-S12** — [Software Engineering at Google — Chapter 12: Unit Testing](https://abseil.io/resources/swe-book/html/ch12.html). Book 2020; live HTML chapter. Локаторы: Test via Public APIs; Don’t Put Logic in Tests (Examples 12-15/12-16); Defining Test Infrastructure. Тип: Первичное описание инженерной практики Google.
- **DAT-S13** — [Hypothesis: Domain and distribution](https://hypothesis.readthedocs.io/en/latest/explanation/domain.html). HTML banner observed: Hypothesis 6.170.14; /latest is mutable. Локаторы: How should I choose a domain for my test?; Why not let users control the distribution?. Тип: Документация автора property-based testing framework.
- **DAT-S14** — [Hypothesis: Replaying failed tests](https://hypothesis.readthedocs.io/en/latest/tutorial/replaying-failures.html). HTML banner observed: Hypothesis 6.170.14; /latest is mutable. Локаторы: The Hypothesis database; Using @example to run a specific input; Prefer @example over the database for correctness. Тип: Документация автора framework.
- **DAT-S15** — [Hypothesis: Stateful tests](https://hypothesis.readthedocs.io/en/latest/stateful.html). HTML banner observed: Hypothesis 6.170.14; /latest is mutable. Локаторы: You may not need stateful tests; Rule-based state machines; DatabaseComparison example. Тип: Документация автора model/stateful testing framework.
- **DAT-S16** — [Application of property-based testing tools for metamorphic testing](https://arxiv.org/pdf/2211.12003). arXiv:2211.12003v1, 2022-11-22; accepted ENASE 2022 preprint. Локаторы: §2 Background, PDF pp.2–3; §4 Proposed Approach, PDF pp.4–6. Тип: Первичная исследовательская работа.
- **DAT-S17** — [Stryker: Mutant states and metrics](https://stryker-mutator.io/docs/mutation-testing-elements/mutant-states-and-metrics/). Live official documentation. Локаторы: Mutant states; Metrics; Test states and metrics. Тип: Определения метрик инструмента.
- **DAT-S18** — [StrykerJS: Disable mutants](https://stryker-mutator.io/docs/stryker-js/disable-mutants/). Live official documentation; disable comments noted since 5.4. Локаторы: An example (equivalent max mutant); Disable mutants; Using a // Stryker disable comment. Тип: Документация инструмента.
- **DAT-S19** — [scikit-learn: Common pitfalls and recommended practices](https://scikit-learn.org/stable/common_pitfalls.html). HTML banner observed: 1.9.1; /stable is mutable. Локаторы: §12.2 Data leakage; §12.2.1 How to avoid data leakage; §12.2.2 Data leakage during pre-processing. Тип: Официальное практическое руководство ML library.
- **DAT-S20** — [Google Benchmark User Guide](https://google.github.io/benchmark/user_guide.html). Live official guide; release tag not stated. Локаторы: Timing and Repetition Control; Runtime and Reporting Considerations; Manual Timing; Preventing Optimization; Reporting Statistics. Тип: Документация microbenchmark framework.

## Ограничения доступа

Не использованы как полнотекстовая опора: ACM badging (403), Googleblog change-detector (challenge redirect), две отсутствующие/недоступные tutorial-страницы Hypothesis, ранний MT PDF arXiv:2002.12543 (искажённый текст; screenshot-инструмент не предоставил видимое изображение), HKU TR-2017-04 (timeout), ScienceDirect S0950584926001394 (403). Отказы не обходились; источники заменены отдельными доступными первичными публикациями. Детали каждой попытки — в `sources.json`. Для metamorphic-критерия использован читабельный авторский PDF arXiv:2211.12003v1, §§2,4, а не search snippet.

## Что выполнено и чего не делалось

- Выполнены интернет-исследование, чтение разделов, техническая интерпретация и локальная проверка согласованности трёх артефактов.
- Проверка JSON: 11 уникальных критериев, 20 уникальных источников, все source_refs разрешаются, обязательные поля присутствуют. Два иллюстративных контрпримера (deduplicating sort и constant idempotent normalizer) дополнительно проверены короткими независимыми stdlib-вычислениями; E02 код и данные в них не использовались.
- Текущая baseline v2, её 127 пакетов и интеграционные сценарии **ещё не аудированы этим агентом**; repository/product code не исследовался.
- Спецификации и продукт не изменены; native services, установки, продуктовые тесты и внешние записи не выполнялись.
- Следующий шаг для корневого review: заморозить/объединить критерии, затем применить к реальным current-v2 contracts, сохраняя distinctions applicable-covered / applicable-gap / bounded-partial / not-applicable / unresolved.

