# Критический разбор и уточнения архитектурного видения

Research proposals, 2026-10-20. Существующие ADR и ratifications этим текстом не изменяются.

---

## 1. Что сохраняется

Основная архитектурная позиция остаётся: универсальная grammar, B-on-A, reuse-first, discovery вместо domain allowlists, причинное проектирование, lifetime custody и обучение. Внешний корпус помогает реализовать это видение; отдельная sovereign платформа управления «истиной» для него не нужна.

Принятые [ADR-0160](../../../adr/0160-evidence-portfolio-independence-multiverse-synthesis.md), [ADR-0166](../../../adr/0166-evidence-acquisition-decision-boundaries.md), [ADR-0172](../../../adr/0172-balanced-memory-influence-ledger.md) и [ADR-0174](../../../adr/0174-policy-evidence-capability-graph.md) уже дают большую часть необходимых механизмов на уровне решений: portfolios/multiverse, eligibility-before-VOI, bounded learning influence, construct-first discovery. Здесь не установлена полнота их реализации.

## 2. Предложения по формулировкам ориентиров

### P-A. «Всё сводится к данным» — утверждение о представлении

**Риск:** из машиночитаемой формы сделать вывод, что любые основания можно заменить дополнительными наблюдениями.

**Предлагаемое уточнение:** «Все основания должны иметь обрабатываемое представление, но их epistemic role и authority не сводятся к наблюдениям. Causal relation, методологическая конвенция, normative mandate, permission и institutional act требуют своих оснований и не выводятся из объёма данных».

Это разъяснение уже принятого [W5-K01](../../../system-design-decisions/wave5-evidence-substitution-ratification.md), а не новый вид authority. Рекомендуется добавить его в стратегическое изложение рядом с data-first принципом.

### P-B. Растущая world model может хранить конкурирующие структуры

**Риск:** единственное число «SCM» прочитывается как обязанность преждевременно выбрать единственный истинный graph.

**Предлагаемое уточнение:** «World model — versioned совокупность совместимых частей и явно конкурирующих causal hypotheses с областью применимости, evidence и unresolved relations. Point identification желательна там, где обоснована; partial identification, contested structures и abstention остаются полноценными исходами».

Это содержательное уточнение [north star](../../../system-design-decisions/policy-design-causal-operating-system-north-star.md), §§2–4. Оно не требует общего численного posterior по всем моделям: вероятности между структурами допустимы только при определённом и обоснованном probabilistic model. Неполное знание не обязано маскироваться смесью с произвольными весами.

### P-C. Model intervention и институциональное действие — разные звенья

**Риск:** `do(X)` выглядит как уже доступная и детерминированно исполнимая политическая мера.

**Предлагаемое уточнение:** «Model-side operator описывает изменение в выбранной модели. Реальный policy lever связан с ним отдельным implementation mechanism: competence → act → delivery → take-up/compliance → изменения состояний. Исполнение и его неопределённость входят в обоснование, но внешние институциональные функции не переходят к PolicyOS».

Отделение внешних актов следует из [S0-K03/K04](../../../system-design-decisions/stage0-custody-kernel-ratification.md). Явная связь с интервенционным атомом улучшит strategic north star. Это не предложение сделать PolicyOS executor.

### P-D. Обучение всегда указывает, что именно изменилось

**Риск:** любое расхождение prediction/outcome автоматически обновляет causal model; popular sources становятся истиннее, а часто выбранные ценности — обязательнее.

**Предлагаемое уточнение:** «Discovery ranking, method applicability, empirical model и понимание институционального контекста обучаются раздельно. Causal update требует разрешённого диагноза; memory не даёт current evidence; learning preference evidence не назначает value mandate».

Это следует из W5-K03 и ADR-0172. Новое здесь — связанное изложение, а не новый слой governance. Политическая дискуссия и изменение авторизованных целей тоже возможны, но имеют собственный источник и время, а не происходят незаметно через optimiser feedback.

### P-E. Универсальность не требует отсутствия engineering extensions

**Риск:** требование «новое знание без изменения кода» превращается либо в скрытый allowlist поддержанных типов, либо в небезопасный запуск произвольного метода из публикации.

**Предлагаемое уточнение:** «Новые сочетания известных operators и новые corpus records должны обнаруживаться без domain-template whitelist. Если новый метод требует нового исполняемого operator, протокола или verifier, это явное capability extension с полной цепочкой admission и проверки. Незнакомое содержание может оставаться доступным candidate reasoning до появления такого механизма».

Это согласуется с Rule 12 organizing rules: discoverable, executable и admitted различаются. Универсальная система учится расширять средства, а не объявляет заранее реализованным любое средство.

### P-F. Рост знания может уменьшить допустимость прежнего утверждения

**Риск:** learning и corpus growth оцениваются только ростом числа green outcomes.

**Предлагаемое уточнение:** «Коррекция, контрсвидетельство, новая применимая норма или обнаруженная зависимость могут сузить вывод, изменить ranking или потребовать отзыва/переоценки. Это корректный результат обучения. Исторический replay сохраняет исходную basis; текущая публичная позиция меняется через владельца custody».

Это следует из identity/custody и W5, не вводит требования отозвать всё при любом изменении bytes. Materiality определяется по конкретной зависимости и rule.

## 3. Атаки и внесённые исправления

| Атака | Контрпример | Исправление в пакете |
| --- | --- | --- |
| Каталог незаметно стал онтологической границей | Источник не входит в EF-* и теряется до candidate discovery | EF-* editorial; unknown family допускается; future discriminator проверяет неизвестный facet |
| Карточка стала знаком authority | Подписанный, но неприменимый акт проходит как governing law | Source, extracted ground и task use раздельны; correspondence остаётся candidate до установления adjudicator и positive acceptance rule |
| Основания подбираются под желаемый итог | После результата выбрана удобная метрика и названа confirmatory | Predeclared portfolio; adaptive changes сохраняют новую exploratory версию; independent design для confirmation |
| Псевдонезависимость | Несколько обзоров повторяют одну cohort | Study/report lineage, common failure modes; число независимых линий не выдумывается из count ссылок |
| Псевдоконсensus | Процент положительных specifications объявлен probability | Multiverse показывает sensitivity; probabilistic interpretation требует отдельной модели |
| Ценности обучены как власть | Часто встречающийся tradeoff становится default mandate | Preference evidence, hypothetical normative frame и authorized objective choice различаются |
| Закон выбран как модель | Иностранная мягкая норма подменяет применимое ограничение | Юрисдикционная applicability фиксируется; hypothetical reform отдельная policy alternative |
| Поиск выдан за отсутствие знания | No-hit в старом индексе превращается в domain ceiling | Query/release/frontier/cutoff и limitations; recall/freshness отдельно, отсутствие не обобщается |
| Governance gravity | Чтобы добавить источник, требуется новый суверенный registry/gate | Документы исследования + existing corpus owners; редактор обслуживает карту, не authority |
| Privacy через provenance | Queries, rejected candidates или stable IDs раскрывают интересы/людей | Bounded audience projection; hashes не privacy mechanism |
| Обновление причинности по alarm | Drift вызван новым измерением, но обновлён causal coefficient | W5-K03 diagnosis boundary; protective action отделено от causal proof |
| Формальная декларация полноты | JSON валиден, следовательно весь мир покрыт | JSON checks подтверждают только конечный корпус; substantive/runtime coverage не установлена |

Критики получили независимые направления: универсальность/суверенность и search/inference. После их исходных атак выполнена повторная проверка четырёх центральных документов. Уточнены формулировки target architecture, signer identity, privacy search history, unknown-family discovery и confirmation boundary. Это review документации, не native tests или independent runtime verification.

## 4. Что нельзя решить редактурой

По будущим задачам могут действительно требоваться: аутентичный institutional act; legal interpretation компетентного органа; доступ/permission; actual dataset с известным collection process; локальная measurement validation; эмпирическая transport evidence; авторизованный normative choice; доказательство delivery capacity. Атлас может указать путь получения и alternatives, но не создать такие факты своим текстом.

До признания входа внешне недоступным исследователь проверяет существующие corpus refs, открытые первичные источники, допустимые acquisition routes, возможность независимого вычисления и честные условные/частично идентифицированные решения. Если объект по своей природе требует чужого действия, дальнейшая генерация документов не заменит это действие.

## 5. Что пока не ратифицировать

Не вводить универсальную шкалу source trust, один global evidence score, обязательный общий event envelope, закрытый список семейств, автоматическое усреднение values или новый самостоятельный knowledge subsystem. Не назначать numerical independence count без подходящей модели зависимости. Не превращать начальные source cards в product schemas.

Сначала пополнять содержательные объекты и проверять их composition на неодинаковых задачах через existing owners. Когда обнаружен реальный контрактный разрыв, отдельное ADR должно назвать reuse/extend choices, producer/consumer footprint, migration, authority/time semantics и falsifier. Эта последовательность сохраняет интеллектуальную открытость без заявления о несуществующей capability.

Pattern pass: P01/P02/P05/P07/P08/P10/P13/P14/P15/P20/P25/P27/P29/P35/P37/P38. Пакет фиксирует target patterns; implementation status всего репозитория не оценивался.
