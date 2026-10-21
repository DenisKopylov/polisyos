# Протоколы жизненного цикла: проект для реализации

Итог повторного критического разбора, 2026-10-21. Это уточнение [проекта](../11-foundation-lifecycle.md), **не новый принятый SDD, не production schema и не свидетельство выполненных проверок**. Точные владельцы — [карта кода](01-reuse-map.md), source snapshot `635413bcd1bd1d7e7b829d9123765e28e6bf23d6`; перед реализацией сверить delta текущей ветки. [Порядок поставки и различающие проверки](06-delivery-and-review.md) отделены от этого протокола. [Первичные инженерные прецеденты](07-primary-design-references.md) поддерживают отдельные механизмы; их гарантии не переносятся на PolicyOS автоматически.

## 1. Выбор архитектуры и границы контрактов

**Выбор: расширять native owners и соединять их устойчивыми протоколами.** Fabric владеет capture/progress; Core CAS — bytes и выбранными manifest views; предметный owner — смыслом и проверкой отношения; security/retention — разрешённой операцией и размещением копий; Scientist/Claim Ledger/Decision Validity — использованием основания и реакцией нашего claim; runtime — выполнением следующего шага. Не вводить общий GroundService, вторую систему статусов, глобальный permission token или универсальный temporal envelope.

Общее здесь — проверяемые обязательства на переходах, а не одинаковый DTO для всех источников. Названия «подготовлен», «неоднозначен», «закрыт частично» далее описывают состояния протокола: **не добавлять их как новый public enum без проверки существующих типов и composition rules**. Remote computation может не иметь локального raw; открытый файл — индивидуального grant; историческое исследование — обещания currentness. Применяются только относящиеся к выбранной операции обязательства.

| Граница | Обязательство производителя | Что проверяет принимающий owner | Устойчивый результат |
|---|---|---|---|
| Запрос → capture | Зафиксировать источник, selector, protocol/profile, ограничения и допустимый доступ | Что фактический маршрут соответствует запросу и разрешённой операции | Attempt и receipt полученного, включая частичный/неоднозначный исход |
| Capture → release | Связать полученные members с cut/coverage и native continuity | Читаемость выбранных members, правило завершения, ограниченность гарантии | Immutable root фактически полученного и отдельная оценка completeness |
| Resource → relation | Сохранить occurrence, преобразование, assertion и ограничения | Отношение к конкретному proposition/use, а не наличие ref | Предметный assessment с exact inputs/rule и областью действия |
| Relation → claim use | Зафиксировать использованную basis и необходимые предикаты | Content binding, смысл, допуск, зависимости и допустимую текущесть | Owner-native use/admission и dependency enrollment |
| Use → public projection | Завершить owner commit и предоставить защищённое чтение | Текущий head, applicable generations, audience и disclosure | Проекция именно нашего claim в установленной границе |
| Change → reaction | Сохранить событие/отношение, не присваивая reaction источнику | Какие uses материально затронуты; что делать с неизвестным scope | Append-only действие canonical owner, а не статус job |

До реализации нужен census реальных producer/caller/consumer путей затронутого механизма. Эти строки не доказывают, что перечисленная композиция уже существует. Включать mandatory API/CLI/export/generated/browser companions по фактической поверхности; не требовать UI для сугубо внутреннего перехода, если audit/API поверхность явно достаточна.

## 2. Захват: cut, непрерывность и точное чтение

### 2.1. Что делает продолжение тем же capture

В native capture record связываются source/collection, selector и фильтры, версия adapter/protocol, source incarnation, выбранная source version/cut, необходимые schema refs и source-native позиции по partition. Incarnation отличает продолжение лога от пересозданного источника с тем же именем. Если источник не предоставляет доказуемую continuity identity, это ограничение resume, а не повод придумать её из URL.

Logical operation, attempt и receipt различаются. Повтор одной операции может дать новый ответ; одинаковый hash не означает то же событие. Event identity задаётся source protocol — например, incarnation + partition + log/transaction position + key/operation. Секретные cursor/lease/credential locators остаются в защищённом owner storage; публичный digest такого токена не считается безопасным автоматически.

Продолжение допустимо, только если selector, incarnation, cut, schema interpretation и boundary rule совместимы с сохранённым checkpoint. Изменение фильтра, сброс источника или истечение replay-log начинает новую generation либо явно разрывает continuity. Нельзя сравнить offsets разных incarnations как одну шкалу.

### 2.2. Snapshot и изменения после него

Предпочтителен самый простой поддержанный источником вариант:

1. **Согласованный snapshot и log cut.** Snapshot описывает состояние на cut C; adapter доказывает включение всех релевантных committed changes между C и выбранным F, с явными inclusive/exclusive границами.
2. **Перекрывающиеся chunks и CDC.** Только если adapter реализует собственный протокол overlap: границы окна, стабильные ключи, порядок snapshot-read/update/delete, правила столкновений и ограничения schema changes. Поздно доставленная snapshot-строка не должна воскресить уже удалённую запись.
3. **Наблюдение интервала без такой гарантии.** Сохранить полезный результат с declared consistency/coverage limit. Завершение обхода mutable API не превращает его в snapshot.

Continuity — **свойство протокола**, не арифметическая плотность offsets. WAL positions, filtered topics и opaque cursors могут законно иметь промежутки. Проверка использует source receipts/ranges/checkpoints, необходимые transaction boundaries и подтверждённую область фильтра. Если источник не позволяет установить целостность транзакции, не обещать её. Fixture `10,12` свидетельствует о пропуске `11` лишь для специально заданного dense protocol.

Раздельно сохраняются: закрытие обхода; согласованность snapshot; coverage выбранной области; source-log progress; event-time watermark; время последнего наблюдения. Idle partition или большой watermark не доказывают полноту источника. Empty poll, `304`, `404`, отсутствующая строка в partial listing и подтверждённый delete — разные факты. Delete/truncate/key-change применяются по native order и scoped membership, а не по времени доставки.

### 2.3. Commit и recovery

Последовательность: persist capture intent → bounded fetch → persist permitted member/page и receipt → verify binding → advance acknowledged progress. Cursor не может обогнать durable data. После crash между member и progress возможен повтор с reconcile; после progress без доказуемого member — continuity не подтверждена, а не «почти complete».

Перед seal root сверить ожидаемые partitions/страницы/диапазоны с полученным **по доказуемому source scope**, разрешить overlap/schema/delete, проверить exact child refs. Закрытый root означает immutable список результата. Полный denominator внешнего источника — отдельное утверждение с собственным основанием. Budget stop, недоступная partition и потерянный log дают scoped partial/continuity loss. Root с `complete=true`, но без подтверждения его premise, не проходит protected consumer.

Consumer читает root + выбранные manifest/profile/schema + cut/frontier по native протоколу; не смешивает `latest` из нескольких stores. Для нескольких источников получается **вектор cuts**, а не глобальная транзакция. Требуемую task-level совместимость — период, допустимый skew, популяцию — проверяет owner. Нет нужного correspondence — условная/ограниченная композиция, без выдуманного simultaneous snapshot. Если retained snapshot исчез, exact replay становится unavailable; нельзя незаметно взять новый.

### 2.4. Конкурентный frontier commit и HTTP continuation

**Один partition head — один fenced writer.** Fabric cursor owner связывает key с incarnation, selector/profile и partition; Runtime attempt даёт текущий fence. Запись progress сравнивает active fence **и expected prior frontier/root в момент commit**, а не только при выдаче lease. Поздний A не может заменить committed result B после reclaim/cancel. Persist members до conditional head update; orphan bytes reconciled отдельно. Между CAS и control store нет предполагаемой общей транзакции: durable stage/reconcile из §2.3 обязателен. Source positions сравниваются только в рамках их native order; fencing epoch не подменяет source cut.

Bounded observation @C: `fabric/data_plane/cursor_store.py::save_partition_state` сериализует index write file lock-ом, но заменяет `(plan_id, partition_id)` без expected-head comparison; `core/contracts/cursor.py::PartitionCursorState` не содержит typed attempt fence. Это подтверждает нужду сверить данный seam при A0, не живой race или отсутствие иных защит во всём продукте. Future probe: pause A → B commits → resume A → fresh reader остаётся на B; удалить compare/fence, оставив поля, — probe должен различить потерю свойства. UNRUN.

**HTTP resume выбирается per source, не автоматически.** Adapter связывает final representation, relevant `Vary` request fields, content coding, strong validator/поддержанный immutable object identity, range unit/bounds/total и completion. Для стандартного `Range` append допускается только после проверки `206`/`Content-Range` и совместимой сильной identity; ignored Range (`200`), смена варианта, слабый validator или неподдержанный partial protocol требуют нового bounded capture либо honest partial. Offset относится к content-coded representation, не длине уже decoded prefix. Собрать encoded bytes до decode либо использовать доказанный codec checkpoint; произвольный compressed suffix самостоятельно не декодируется. Если raw retention запрещён, разрешён decoded-only derivative с source/decoder binding, но без неподдержанного exact range replay.

Strong ETag — continuity assertion источника, не независимое доказательство snapshot при недобросовестном origin. Сохранить это provenance различие; authority predicate о внешней полноте/неизменности требует своего admitted основания. Локальный hash доказывает полученные bytes. Complete-GET oracle должен относиться к тому же закреплённому source version и request variant, не произвольному позднему ответу.

Считать encoded input и decoded output на соответствующих слоях, не по одному `Content-Length`; streaming decoder и archive expansion также ограничены. Transport framing/TLS не смешивать с representation hash. Protocol basis: [RFC9110 §14.1.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-14.1.2), [RFC9111 §§3.3–3.4](https://www.rfc-editor.org/rfc/rfc9111.html#section-3.4). Это требование проекта, не implemented generic resume. @C `HTTPConnectorBase` создаёт aiohttp session без override decompression; [документация 3.13.3](https://docs.aiohttp.org/en/v3.13.3/client_reference.html) задаёт auto-decompress. Поэтому счётчик полученного library body не подтверждает оба ceilings. Future falsifier: сменить coding/ETag/returned range посередине, high-expansion body, restart между ranges; полный hash должен совпасть с выбранным complete GET только у корректного capture. UNRUN.

## 3. Смысл: assertion, assessment, use и выбор основания

### 3.1. Одна ссылка не доказывает отношение

Связать три различных факта в существующих предметных типах:

- **Assertion:** кто утверждает какое отношение между exact occurrences/propositions/outputs; owner-local relation/profile; направление, source version/span, relevant context и собственная provenance.
- **Assessment:** какой predicate действительно проверен каким методом/правилом, на каких inputs, с какими limitations. Проверка bytes, entailment, applicability, empirical calibration и полномочия — не один predicate.
- **Use:** для какого claim/purpose/estimand/audience и frozen task basis owner принял этот assessment; какие зависимости и альтернативы были существенны.

Это не три обязательных новых класса. Сначала использовать `DocMeta`/`DocFragment`/`CitationRef`, existing Scholar/Lex/Foundry evidence, ClaimRecord/ledger и artifact input edges. Узкий owner-local artifact добавляется лишь там, где реальный consumer не может выразить связь. Semantic relation может образовывать цикл возражений; derivation immutable outputs остаётся DAG. Equality, coreference, conflict и correspondence нельзя объединять одним traversal или `same_as` по строке.

На pinned C `scientist/validation/claim_support.py::_satisfied_predicates` выводит ряд satisfied predicates из непустых refs/строк; это **диагностика формы в данном evaluator**, не content entailment. `ComparisonOptionRecord` в `scientist/evidence/claims/models.py` ограничивает арифметику support counts, но сам не вычисляет независимость. Новая цепочка не вправе повышать authority этими stand-ins. Перед изменением определить callers и downstream checks: наличие более сильного consumer нельзя ни предположить, ни отрицать по одному файлу.

Проверка независимости нужна в той степени, в какой она заявлена или необходима выбранному методу. Same-code rebuild устанавливает согласованность, сам по себе не доказывает правильность метода или scientific validity (S0-K14). Ни всем hashes/parser checks внешний appointment, ни любому `independent=true` доверие не нужны. Контентно связанный запуск конкретного predicate и его provenance — обязательная основа заявленного результата.

### 3.2. Разнородные основания и отрицательные утверждения

| Пример | Сохраняемое различие | Что не допускается |
|---|---|---|
| Интервью/местное знание | Участник, контекст, метод получения/кодирования, допустимый scope, альтернативное толкование | Превратить одну цитату или частоту в голос всего сообщества |
| Норма права | Официальный text/act, candidate interpretation, warrant, applicability и selected use | Вывести допуск из наличия legal URL или обновить старый период новой нормой |
| Социальная метрика | Construct, методика, population, unit, classification, направленное correspondence и потери | Считать одинаковые имена/column IDs доказательством равенства Gini, Atkinson или обновлённой классификации |
| Исправление статьи | Notice → конкретный результат/версия; scope может быть неизвестен | Автоматически отозвать все положения статьи либо проигнорировать notice без exact match |
| Несколько исследований | Общие observations/cohort/model/calibration и неопределённый overlap | Считать число документов числом независимых подтверждений |
| Отрицательный вывод | Domain/quantifier, coverage/detection opportunity, метод/threshold, cutoff, blind spots | Слить «не найдено», «не изучалось», «не обнаружено» и «установлена эквивалентность» |

Effective independence count, если метод действительно его использует, — результат versioned estimator над declared dependency denominator, а не универсальное целое свойство корпуса. Частичная зависимость может требовать covariance/model/sensitivity, а не механического collapse по одному author/cohort ID. Unknown overlap не считается установленной независимостью, но не запрещает условный анализ с явной моделью зависимости.

### 3.3. Обучение и несколько bases

Scientist сохраняет альтернативные basis branches как сравнимые условные программы: shared inputs отдельно от изменяемой методики, value premise, legal hypothesis или measurement rule. Права на реальное действие и действующее право не оптимизируются по желаемому ranking; hypothetical reform допустима как явно условная ветка.

Память поиска может менять queries, набор рассматриваемых методов и стоимость acquisition. Она не становится дополнительным evidence. **Её влияние на отбор — материальная зависимость процедуры**, но глубина trace определяется заявленным результатом. Exploratory run может сохранять bounded trace memory/rule version, наблюдённого frontier, policy выбора, selected inputs, budget/cutoff и gaps; полного rejected corpus для разрешения exploration не требуется. Confirmatory/public consumer получает selection process и denominator, необходимые его inference contract. «Лучший среди всех допустимых» требует соответствующего полного scoped frontier либо явного ограничения. Не хранить каждый LLM token и private rejected payload: permitted refs/reason codes достаточны, если устанавливают нужное свойство. Отсутствие требуемого selection contract нельзя заменить меткой «memory не evidence».

Отзыв/ограничение исходного материала отдельно запускает оценку retained summaries, retrieval indexes, fine-tuned/model artifacts и learned routing priors. Не обещать универсальное machine unlearning из одного source-delete. Если влияние нельзя локализовать или удалить доказуемо, ограничить affected use/retire производный model по owner rule и показать точную unreplayable/unlearning limitation; не переписывать историческую методику задним числом.

### 3.4. Обучение не делает использованные outcomes независимой проверкой

Method/evaluation owner связывает выбранный inferential claim с frozen target/outcome cut, model/training generation, **фактической доступностью и exposure данных при выборе**, историей существенных queries/results и применимым holdout/adaptive-inference rule. Дата публикации не доказывает дату первого exposure. Полный trace и `contamination_check=pass` не корректируют adaptive selection сами по себе. Reuse exposed outcomes допустим для exploration; для confirmatory inference нужен применимый метод коррекции либо нераскрытый evaluation basis с достаточным design. Если история внешней pretrained модели неизвестна, не требовать вымышленного полного журнала: ограничить заявляемую независимость, выбрать иной validation design.

Выбор method-specific correction остаётся у existing Scientist/method owner, без universal holdout service. [Dwork et al., 2015](https://proceedings.neurips.cc/paper_files/paper/2015/file/bad5f33780c42f2588878a9d07405083-Paper.pdf) показывает риск адаптивного переиспользования holdout и один подход к его контролю; не все данные или методы удовлетворяют его предпосылкам. Future probe: один outcome repeatedly influences selection, затем назван validation; consumer ограничивает inference даже при неизменных audit markers. Supported correction/unexposed basis даёт положительный сценарий. UNRUN.

**Внешний publisher не делает feedback экзогенным.** Связать нашу generation/recommendation → institutionally supplied act/assignment → actual exposure/non-take-up/measurement → observed outcomes. External owner устанавливает факт действия; PolicyOS не приписывает ему принятие рекомендации. Scientist/Foundry учитывает selection, spillovers, measurement changes и counterfactual в выбранном update. Эти наблюдения полезны, но без достаточного design не являются независимым causal corroboration собственной рекомендации. [Perdomo et al., 2020](https://proceedings.mlr.press/v119/perdomo20a.html) исследует изменение распределения под влиянием предсказаний; наша конкретизация — сохранять этот путь зависимости, не запрещать post-deployment learning. Пересказ нашего output внешним сайтом также не создаёт новое эмпирическое основание. Future probe: удалить recommendation→exposure связь, оставить настоящий внешний report; факт отчёта сохраняется, необоснованный independence claim не проходит. UNRUN.

## 4. Изменение основания, отсутствие сведений и публичная текущесть

### 4.1. Dependency set шире списка использованных файлов

Use зависит от конкретных объектов **и от предикатов над множествами**. Примеры: «в выбранном реестре нет запрета», «все подходящие studies включены», «лучший вариант среди найденных», «после cutoff нет применимого исправления». Новая запись способна изменить такой вывод без изменения единого старого artifact ref.

Негативная/set dependency связывает owner corpus/namespace, selector/predicate и его version, выбранную generation/coverage, scope права видеть набор, query coordinates и смысл утверждения. Не сохранять произвольный SQL как автоматически исполнимый authority gate. Реальный owner реализует известный predicate и его invalidation scope. Search/no-hit остаётся ровно scoped no-hit; неполный корпус не поддерживает утверждение об отсутствии во всём мире.

Первый корректный impact index может быть **грубым**: scope/collection generation invalidates все uses с таким set dependency. Более точный range/predicate index — последующая оптимизация. False-positive rechecks допустимы; false-negative invalidation — нет. Полный denominator schema+ledger не покрывает невыраженную семантическую зависимость: её нужно моделировать либо объявить границу claim. Не требовать универсального predicate-lock manager на все внешние источники.

### 4.2. Порядок publication и change processing

1. Подготовить exact basis и assessment; записать owner use и все материальные object/set/rule/access dependencies. В качестве root выступает существующий claim/basis owner, не новый world registry.
2. Связать input cut с source-owner generation и replay position C. Source-owner journal append и продвижение его generation — один commit. При enrollment owner устойчиво регистрирует consumer с high-water W и гарантией replay/delivery строго после W; catch-up покрывает (C,W]. События после W остаются доступными этому consumer, даже если live attachment задержался. Consumer cursor продвигается только после committed effect. Если C ниже replay floor или соответствие input cut позиции C не доказано, current admission недоступен до нового capture/reconciliation. Проверять no-gap по owner journal, а не по consumer-флагу «caught up». Slow reverse index — accelerator, не ground truth.
3. После catch-up finalize claim head по протоколу, который сериализует проверку актуальных generations и commit с writers этих generations. В одном owner store — транзакционный compare/commit; между stores — только реально общий fencing/serialization protocol всех участников либо durable preparation/reconciliation с явно ограниченной currentness. Стабильный порядок захвата guards решает лишь deadlock, не заменяет этот протокол; см. [исходную границу owner-writer fence](02-flow-and-consistency.md). Не держать distributed lock во время fetch/LLM/model compute. Порядок handoff определяется commit/journal order, не source occurred_at.
4. До завершения записи/связи не выпускать unqualified current head. Если backend не даёт нужной гарантии, выпускать только разрешённую cutoff-qualified projection; недостающий доступ/обязательный допуск нельзя обойти словом cutoff.
5. Change delivery использует committed consumer outcome: не ставить окончательный dedupe marker до устойчивого применения события. Один transaction для marker+effect либо recoverable журнал стадий. Crash после marker и до index/cascade не должен навсегда потерять реакцию.

Source-side fence относится к **известным локальным custody generations**, не к ещё не наблюдённому внешнему миру. Один owner не может выдать вечный token на law, право или source freshness. Разнородные dependency generations сохраняют native semantics; их не сравнивают как глобальный числовой clock.

Если snapshot/CDC source и local owner journal используют разные позиции, C в этом handoff — **local position с доказанным соответствием source cut**, не численно равный remote offset. Adapter сохраняет receipt соответствия snapshot cut → native continuity frontier → local admitted journal position. Он устанавливает отсутствие потерянного source interval до enrollment W; local пустой журнал этого не доказывает. Если native retention уничтожила промежуток до attachment, нужен новый supported snapshot/overlap, иначе observation/candidate с заявленной границей. Не вводить всеобщий total order внешних sources.

### 4.3. Current read не ждёт scheduler

Fresh authority-bearing reader проверяет завершённый claim head, generation basis и относящуюся к обещанию time/freshness policy. Durable owner journal фиксирует изменение раньше, чем медленный fanout успеет пересчитать все claims. При lag reader отказывает **в затронутом current assertion**, выдаёт разрешённую историческую/cutoff-qualified view или pending limitation. Scheduler нужен для восстановления полноты ответа, а не для правдивости до его запуска.

**Точка чтения задаётся явно.** Default первого slice — consistent owner transaction/guard, охватывающий claim head, dependency generations и построение возвращаемой projection; все relevant writers участвуют в той же границе. Ответ сообщает выбранный cut/observation, а не обещание вечной текущести после ответа. Для нескольких stores два одинаковых reads не являются default доказательством: допустимый snapshot algorithm должен установить общий read cut, отсутствие ABA, monotonic generations, complete participant set, head binding и recovery. Даже доказанный optimistic snapshot устанавливает состояние на своём cut, но не защищает последующий publication/action commit — там требуется §4.2 или соответствующий operation fence. Без доказанного протокола — только разрешённая cutoff-qualified view/отказ в current assertion. Permission/disclosure проверяются по §5.2; historical cutoff их не обходит.

Если наступил recorded expiry/revalidation bound и scheduler выключен, старый cached green не продлевается. Проверка времени использует объявленную clock/skew policy; при непригодном clock нельзя обещать strict temporal predicate. Refresh due не доказывает ложность факта: owner определяет, что именно стало unavailable — currentness, protected use или иной predicate. Не превращать всё просроченное в универсальное `false`.

Каскад обрабатывает сначала scope/epoch invalidation, затем bounded material re-evaluation. Coalescing нескольких событий разрешено, если сохраняется нужная история и новая проверка покрывает их смысл. Retraction→restoration нельзя стереть до одного «latest normal», если между ними было наше опубликованное действие. Циклы relations обрабатываются по owner/generation с конечным visited set; budget stop остаётся pending и видимым. Ни event storm, ни недоступность очереди не дают зелёный current head.

Committed publication/effect хранит разрешённые causal refs к actually used basis, rights decision/generation и operation admission. При compaction сохраняются эти минимальные связи и reconciliation/floor evidence в пределах обещанного и разрешённого history; порядок разных owners не восстанавливается сортировкой wall timestamps. Потеря связи означает history/replay limitation, а не чистый audit. Если вся decisive control dependency недоступна, detailed durable limitation тоже может быть недоставима: доступный API выдаёт ordinary unavailable; никаких cached current positives. Reason-specific projection появляется после reconciliation либо через уже существующий независимо проверенный путь. Integrity не означает availability при полном отказе store.

Public consumer использует существующий контракт [PV-K01–PV-K09](../../../../system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md), не общий `Verified=true`. Раздельно сообщаются issuance authenticity, projection faithfulness, public-history establishment, durable verifiability, current authority, status-snapshot selection и evidence obtainability. Historical issuance не стирается утратой текущего допуска; сохранённая подпись не доказывает projection faithfulness. PV-K04/PV-K05 требуют conservative protected-query parity и сохранения material negative/terminal outcomes; PV-K09 включает proof metadata в disclosure. Неустановленный требуемый predicate не становится positive. Если public surface вне slice, указать `surface_out_of_scope`, existing owner/contract и запрет переносить internal PASS в public authority.

## 5. Права и копии: write fence, отзыв и restore

### 5.1. Изменение условий не равно автоматическому отзыву

Источник сообщает новую лицензию/условия; компетентный rights owner определяет **применимость** к конкретному grant, операции, purpose, recipient и времени. Уже выданный irrevocable grant, иной правомерный basis или будущая effect date могут изменить результат. Ни «последняя лицензия запрещает», ни «какой-то grant разрешает» не решают конфликт без applicable precedence rule. Неизвестная применимость ограничивает зависимое protected use; это не разрешение сделать юридический вывод за институт.

После принятого применимого ограничения owner меняет scoped rights generation. Admission захвата, хранение, transform/index, remote submission, использование в claim и disclosure — разные операции. В каждой проверяются именно действующие ограничения. Same-tenant и same-hash не разрешают другой case/purpose. Identity/hash не несут права сами по себе.

### 5.2. Копия появляется только внутри enrolled write path

До нового CAS/index/cache/temp/provider write storage owner устойчиво связывает operation intent, разрешённый use, output namespace, rights generation и retention basis. После durable записи — content/placement receipt. Неизвестный исход остаётся в reconcile как possibly-written; отсутствие receipt не доказывает отсутствие bytes.

Final commit/output-head и соответствующий rights writer участвуют в общем owner fence. Отозванный generation не может завершить позднюю видимую копию. Если bytes уже записаны вне SQL, они остаются изолированными и учитываются до разрешённого завершения/удаления. Старый cached allow не продлевает разрешение. Перепроверка перед вызовом без защиты последующего commit — недостаточна.

Гарантия изоляции относится к **staged result path**: provider private staging или actual receiver gate действительно удерживает видимость до admitted head. У provider с немедленно видимым эффектом она не возникает из нашего intent. Такой path допускается только как отдельная уже разрешённая operation с явно принятым dispatch/admission point и truthful indeterminate outcome; он не удовлетворяет контракту atomic publish-after-local-commit. Если конкретный protected use требует именно отложенной видимости, этот provider path unsupported. Потерянный ответ не доказывает отсутствие раскрытия, а поздний revoke не отзывает уже совершённый внешний эффект.

Для read/stream/export явно задать **границу авторизации операции**: до первого disclosure и на безопасных bounded продолжениях, по policy владельца. Не обещать отозвать bytes, уже переданные читателю. Невозможность остановить удалённую операцию — отдельный indeterminate outcome с reconcile, не локальный rollback. Отказ/ошибка/graph degree/hash также не должны раскрывать скрытое основание.

Projection read cut и permission check при подготовке buffer — не admission фактической выдачи. Existing security/publisher owner задаёт linearization point для передачи result waiter/выходному reader и bounded chunk: applicable revoke, упорядоченный раньше admission, запрещает эту выдачу; admission раньше revoke разрешает лишь явно поддержанный in-flight scope/duration/volume. Проверка и admission сериализованы с rights writer; все cache/future/export paths проходят эту границу. Уже переданные transport/внешнему consumer bytes не отзываются. Если governing policy требует более сильного прекращения передачи, нужен поддерживающий его transport/owner protocol; простое recheck-before-send не доказательство. Без порядка/разрешённой in-flight semantics protected disclosure недоступен, historical cutoff не обход. Не держать глобальный lock на время network delivery.

### 5.3. Удаление и восстановление

После use fence retention owner перечисляет enrolled placements и сверяет фактические controlled stores: raw, transformed content, index/embedding, temporary shard, job/provider files, exports, audit/backup и их generations. Нужен census write/restore paths, включая сторонние библиотеки, а не только reachable artifact refs. До такого census нельзя подписать глобальное all-copy deletion.

Каждый owner возвращает фактическую границу действия: удалено; закрыт доступ до expiry; удерживается по действительному hold; provider request/ack; scope неизвестен. Эти факты не складываются в один boolean. Accounting/refcount/tombstone/delete marker не доказывают purge. Cryptographic erase допустим как конкретный backend method лишь при выполненных условиях по всем key/plaintext copies; это не shortcut из названия алгоритма.

Physical dedup разрешён внутри совместимого access/deletion/restore domain. При общем blob сохраняются отдельные logical memberships. Удаление одного membership не должно ломать чужой допустимый use; сохранение общей физической копии не может одновременно называться её уничтожением. При несовместимых обязанностях — изоляция, разрешённая миграция либо bounded unresolved conflict; по умолчанию не дедуплицировать чувствительные copies с несовместимой судьбой.

**Restore сначала quarantined.** Восстановленный namespace получает актуальные rights/deletion decisions из журнала, который нельзя откатить тем же старым backup, затем owner reconciliation и только потом переключение readable head. Если post-backup evidence невозможно получить, нельзя считать его пустым — affected protected reads остаются закрыты. Это не требует бессрочного хранения каждой персональной tombstone: допустимы scoped retained deny records, отказ от старых restore generations или уничтожение всех восстановимых копий/ключей, если такой метод доказуем и разрешён. Перед окончанием retention журнала доказать, что не осталось пути воскресить запрещённое содержимое, либо запретить этот restore path.

Сам restore-head switch участвует в rights/deletion fence: reconciled watermark W/generation сравнивается внутри переключения, а events после W гарантированно доступны enrolled restored consumer. Event W+1 между reconciliation и switch сохраняет quarantine до catch-up. Если stores не дают такой границы, нельзя открывать affected protected reads на основании законченного вчера replay. Restore incarnation инвалидирует pre-restore caches/cursors; прежнее численное значение generation не означает тот же мир.

Anti-rollback evidence должна быть установлена **вне всего фактического rollback closure**, не только в «другом» store, восстановленном из того же backup. Включить material post-backup Claim/public withdrawal/reissue histories наряду с rights/deletion: regrant не воскрешает отозванный head. Если независимая от этого отката freshness/watermark не доступна по существующим разрешённым каналам, affected restore не выходит из quarantine. Не создавать новый privileged authority anchor ради обещания recovery.

Controlled copy census включает реально поддержанные active reader pins, mmap/open-file/native-buffer views и temporary spill. Logical unlink, освобождение disk placement и отсутствие live process copies — разные outcomes. Root/write fence не доказывает отсутствие открытого reader. Drain/подтверждённое termination и permitted lifecycle reconciliation нужны перед соответствующим purge claim; освобождение Python reference не доказывает zeroization памяти. При неизвестных copies — bounded deletion scope, не глобальный успех. Система не обещает отозвать уже раскрытый контент у внешнего получателя.

У WORM/backup/provider могут быть другие сроки и неподконтрольные copies. Показывать их отдельно. Right change не опровергает эмпирический факт автоматически; Claim owner решает дальнейшее использование и public projection. История действий сохраняется в допустимой форме, exact replay после потери inputs не обещается. Ни raw payload, ни linkable digest не становятся бессрочным «безопасным audit» по умолчанию.

Эксплуатационная смена custodian, trust keys или поставщика не является обычным byte refresh. Передача/retirement duties и соответствующие внешние inputs определены в [операционном протоколе](../acquisition/06-operational-continuity.md). Он использует эти же fences, history и fresh projections, не второй lifecycle engine.

## 6. Долгая обязанность, короткие attempts

Стабильная **custody duty** принадлежит native claim/domain owner. Одно **intent** обозначает логическую операцию с неизменным смыслом и inputs. **Attempt** — очередное bounded исполнение на build/protocol версии. **Effect** — один внешний результат, который нельзя дублировать при retry. Effect ID относится к одному side-effect step, включая partition/key там, где это существенно, и immutable request digest; job ID недостаточен для нескольких effects. Эти роли связываются через existing `ControlPlaneStore`, `RuntimeOperationIntent`, worker, outbox и artifact receipts; не создавать новый workflow язык.

| Ситуация | Решение для реализации |
|---|---|
| Ожидание месяцами | Durable due condition; освободить worker и compute lease. При wake заново resolve подходящие inputs/rules/permission. Duty не завершается от закрытия job. |
| Ответ provider потерян | Stable effect ID и request digest; lookup по operation ID или retry в пределах **реального** provider idempotency window. После его истечения не повторять опасный вызов вслепую. |
| Нет lookup/idempotency | Сохранить indeterminate, bounded reconciliation/competent review; другие независимые задачи продолжаются. Нельзя компенсировать эффект, который не установлен. |
| Доставка outbox повторяется | Consumer inbox/outcome и idempotent применение; доставка, receipt, committed effect и ack различаются. Marker+effect атомарны либо recoverable. |
| Отмена | Request, принятое прекращение и фактическая остановка различаются. Existing intent owner сериализует cancel decision с final visible commit/dispatch: cancel выиграл — output inert/quarantined, successor/effect не запускается; commit выиграл — too-late с сохранённой историей. Remote уже отправленный effect может оставаться indeterminate. Lease timeout не доказывает остановку; accounting освобождается после actual stop/reconcile. Это operation semantics, не новый global cancellation status. |
| Rolling upgrade | Intent продолжает compatible pinned protocol/build либо переходит по explicit checkpoint migration с before/after binding. Новая версия кода не меняет law/method basis задним числом. |
| Старый job без effect history | Сохранить известные IDs/events; не дорисовывать историю из retry counter. Неоднозначные in-flight effects сначала reconcile. |
| 429/retry storm | Durable cooldown в фактическом provider/credential quota scope; bounded attempts/age/spend, jitter, due-at. Другие resource pools продолжают работу. |
| Более срочные duties вытесняют остальные | Fair selection с заявленным ресурсом, weights/aging и достижимой service policy; при overload честно ограничить SLO/admission, а не обещать невозможный maximum wait. |

Side effects здесь — только разрешённые получение, remote computation, artifact delivery и другие интеграции внутри ratified identity boundary. Проект не делает PolicyOS администратором, платёжной или notification системой. Compensation, когда она возможна, — новая разрешённая операция, а не стирание истории.

Workflow history хранит разрешённые refs и переходы, не scientific payload corpus. Compaction/Continue-As-New допустимы для execution history, если retained owner history/replay obligations остаются выполнимыми. Сроки попытки, lease, retry, review duty, legal/source effect и retention не объединяются в один timeout.

Unresolved effect сохраняет минимальный разрешённый no-retry binding step/effect identity на всё время, пока любой retained intent/backup может повторить dispatch. Compaction и provider idempotency expiry не обнуляют его. Если хранить binding уже нельзя, owner доказуемо исключает intent из всех управляемых replay/restore paths; иначе такой restore запрещён. Не требовать бессрочного raw payload или linkable digest; не превращать истечение окна в `not_executed`.

Temporal или другой durable engine — **не обязательный новый компонент**. Сначала использовать текущий store/worker; измерить active duties, transition/history growth, recovery/upgrade cost, due lag и требуемую топологию. Если это выходит за согласованный operating envelope, отдельный backend adapter может исполнять те же owner intents. Engine status не становится claim status. В данной работе таких измерений и выбора deployment нет.

## 7. Free grow: совместимость, generations и retirement

До защищённой операции owner сопоставляет requested behavior с фактическими producer, reader и consumer: exact implementation, artifact/schema/codec, semantic rule/profile, required features, разрешённые transforms и resource plan. Это owner-native resolution, не обязательные три новые универсальные `Capability*` DTO. Alias/registry entry помогает discovery; выбранная operation binding закрепляет immutable references.

Unknown optional facets сохраняются namespaced, bounded и inert при разрешённом хранении. Unknown **required behavior** блокирует именно этот protected use; fallback к underlying storage type не устанавливает смысл. Strict authoritative DTO не ослабляется до `dict`. Wire compatibility отдельно от meaning: тот же column ID с новой категорией/population/единицей требует нового semantic binding, даже если parser успешен. Новая версия содержимого, выражающая уже поддержанные отношения, может быть конфигурацией; materially новое вычисление/правило admission требует локального reviewed engine extension.

Optionality даёт только wire behavior. Verified opaque-storage grant может разрешать хранить непонятое целое; это не grant на поздний parse/index/remote submission/disclosure после upgrade. Новый recognizer разрешается и оценивается заново для exact logical membership/use. In-band label не выдаёт права. Parser по умолчанию не получает ambient network/credentials: external refs inert; требуемое разрешение ссылки — отдельный connector acquisition с actual redirect/address policy, source/cut/receipt и budget. Referring document не передаёт свои права вложенному источнику.

**Requiredness определяется consumer request/basis и его owner rule**, не producer-флагом `optional`. Descriptor advertises, actual resolver проверяет; неустановленная материальность ограничивает только соответствующий protected use. В migration chain каждый owner либо сохраняет permitted opaque bytes через existing raw/extension ref, либо указывает точную loss и доступность source root. Не ослаблять strict authoritative DTO; не требовать нового универсального sidecar. Если старое содержимое больше нельзя хранить или читать, новый consumer получает replay/unavailability, а не пустое значение, выданное за отсутствие facet.

Каждая index/materialized-view generation связывает source root, extractor/model/profile/config, visibility и coverage. Build выполняется отдельно; pointer переключается после reconciled completion. Reader pin-ит нужную generation. Обновление source или rights во время build проверяется fence при commit; смешанный index допускается лишь если соответствующий scoped partial profile действительно поддержан consumer.

Отзыв уже promoted semantic generation — material owner change: exact implementation/profile/generation получает durable withdrawal/reassessment event, affected uses dirty до fresh current read. Deployment rollback pointer сам не меняет authority и не чинит G2-based claims. Историческая issuance сохраняется; совместимый G1 может дать новую re-evaluation, но не переписать прежние outputs. Обычный operational rollback без material semantic effect не обязан отзывать все claims.

Resource plan отделяет acquisition bytes/requests, peak memory/state, storage/temporary copies, CPU, concurrency, money и иные действительно применимые ограничения. Streaming ingest не ограничивает память глобального sort/join/graph closure/estimator. Выбрать partition-safe operation, spill, согласованную approximation с error contract или явный budget stop. Approximation нельзя спрятать в «оптимизацию». У metadata, manifests, dependency fanout и verification тоже есть стоимость; root содержит partition refs, а не бесконечный монолит всех строк.

Детализация исполнения и ограничений — [09](09-resource-execution-design.md): bounded queued state, physical enforcement и completion fan-in, transitive parent/child waits, coalescing/retention, cache equivalence и cold recovery. Некалиброванная candidate retrieval допустима с неизвестной recall/ошибкой и явным frontier; inferential/authority use требует достаточного method-specific основания, а не одного слова approximation. [08](08-incidents-and-edge-cases.md) и [10](10-adversarial-review-and-delivery.md) задают составные различающие случаи без новых product enums или выполненных PASS.

Verification cache привязан к predicate и materially relevant tuple. Изменение permission generation требует нового access decision, но не повторного хеширования всех неизменных bytes; новое semantic rule не позволяет reuse прежний semantic assessment, но не делает каждый старый artifact повреждённым. Scope-sensitive cache key и actual verifier inputs выводятся из владельца predicate; нельзя вручную забыть зависимость ради reuse.

Retirement разделяет запрет новых bindings, поддержку уже начатых uses, replay и physical retention. Drain/reconcile in-flight intents; выявить retained claim/manifest roots и enforceable replay duties; выполнить разрешённую derived migration либо явно признать потерю replay. Старые payloads/history не переписывать.

**GC last-check и physical delete сериализованы с root publication.** Простой вариант — существующий storage-owner exclusive barrier от финальной inventory до удаления, если все root/restore writers действительно подчиняются ему. Для concurrent sweep — mark epoch + writer leases, завершение всех writers старого epoch, затем условное tombstone/delete под тем же owner fence; публикация нового root обязана увидеть tombstone и заново установить доступный объект до commit. Внутри этой границы нельзя допустить root между проверкой и unlink. Remote deletion выполняется как recoverable fenced stage, не допускающий resurrect/rebind до reconciliation; истёкшая lease сама по себе не останавливает writer, нужен fencing token. Выбор зависит от реально поддержанных CAS primitives, а не от названия «epoch».

Lagging reverse index/refcount, повторная проверка перед sweep и «давно не читали» недостаточны. Полный controlled root/write/restore census и участие каждого writer — предпосылки; если они не установлены, physical GC в данной границе выключен, bytes retained/quarantined согласно правам. Это не новая глобальная GC-служба и не гарантия удаления provider/backup copies.

Практический free-grow acceptance: второй источник **поддержанного класса** проходит producer→durable result→consumer→change→recovery, остаётся в resource envelope и сохраняет смысл/права. Отсутствие правки central dispatcher полезно как архитектурное свойство, но не как единственное доказательство. Новый protocol/semantic class может требовать кода — локального, а не переписывания платформы.

Pattern pass: P01/P02/P12 — реальные handoffs; P04/P05/P09/P15 — native statuses, authority и warnings; P07/P08 — cut/incarnation/версии/время; P10/P14/P25 — смысл, зависимость и отрицательные выводы; P13/P27/P31 — bounded extensions; P29/P32/P35/P37/P38/P40 — property, complete scope и отсутствие ladder repair. Проект не устанавливает готовность цепочек: [состояние назначается по фактической композиции](../12-acquisition-storage-and-deployment.md#как-читать-итоговую-версию), не по наличию текста или списка probes. Runtime signals этой работы UNRUN.
