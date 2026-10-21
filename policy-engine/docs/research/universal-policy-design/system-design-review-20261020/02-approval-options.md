# Точные предложения на согласование

> Исторический пакет от 2026-10-20. Все перечисленные поправки согласованы 2026-10-21 и применены; актуальный standing — в [записи принятия](03-adoption-20261021.md). Формулировки ниже сохраняют историю выбора.

**Ничего из этого не применено к `system-design-decisions`.** Автор предложения — G, 2026-10-20; исходный commit и хеши — в [document-map.json](document-map.json). Существующие draft, accepted target, ratification и ADR не меняют standing от публикации этого пакета.

Рекомендую принять **A и B** как адресные уточнения; **C01 и C02** — отдельно как осознанные уточнения target; новый SDD пока **не создавать**, сохранив связующий текст в research. Можно согласовать любой пункт независимо. Принятие текста не является приёмкой кода, назначением внешнего reviewer или закрытием finding.

## A. Полная навигация и точный standing

[A-navigation.patch](A-navigation.patch) меняет только README каталога.

**Проблема:** описание всего каталога как pre-ADR слоя противоречит наличию ratified acts; шесть из 19 содержательных документов не включены в таблицу. Reader может принять исторический open item за новое препятствие либо поднять весь draft до standing одного принятого раздела.

**Выбор:** дополнить индекс и явно различить standing документа/раздела, dated amendments и logs. Альтернатива — оставить discovery по поиску; она дешевле сейчас, но воспроизводит путаницу. Цена принятого варианта — поддержание ссылок и статусов без нового registry.

**Основание:** README, frontmatter всех 20 файлов, правила PDC/HDS logs и identity §9.7. Проверка: все 19 документов достижимы из индекса; ratified identity passage не превращает весь North Star в ratified document. Runtime проверки для этого редакционного изменения не требуются.

## B. Уточнения в семи существующих документах-владельцах

[B-owner-clarifications.patch](B-owner-clarifications.patch) содержит **только датированные дополнения**, без переписывания исторических записей.

| ID / документ | Предлагаемый смысл | Что сохраняется |
|---|---|---|
| B01 / North Star | Competing/credal reference уже допустим; `do()` отделён от institutional execution; required grounds шире data; grounding зависит от вида claim | Причинное ядро, intervention atom, candidate freedom и signature boundary |
| B02 / Search target | CI/tier/score/signature — не semantic correspondence; импортированные estimates допустимы в обоснованном scope | Принятый Phase-5 target и reuse-first; не назначается общий adjudicator |
| B03 / Operating model | Portfolio для major empirical claim; adaptive discovery и confirmation различны; record families не allowlist | ADR-0160, обязательные applicable grounds и balanced memory ADR-0172 |
| B04 / Execution topology | Applicability не promotion; A — assurance-role через владельцев, не универсальный арбитр; fresh loop не второй controller | Конструктивный цикл, операция/артефакт и существующие search/acquisition owners |
| B05 / D0-D4 target | Исторический gap map не текущий census; B-promotion не S14; CouplingGraph не доказательство SCM; новые primitives могут потребовать engineering | Accepted B-on-A, draft status остальных частей, открытая grammar |
| B06 / HDS | Provenance/telemetry не claim truth; claim-type grounds, CTM и balanced learning; поздние log closures читаются вместе с ранними pending | Принятые ADR-0147–0155, существующий event envelope, отдельные временные роли |
| B07 / Atlas surfaces | Full material grounds/countergrounds в permitted detail; summary может остаться короткой; readiness не authority | PV audience/disclosure boundary, rich candidate views, отсутствие browser-owned authority |

**B07 включает новый предлагаемый detail-view requirement**, а не только редакционное уточнение. Он требует вашего согласования наравне с остальными пунктами; PV disclosure scope сохраняется.

**Альтернативы:** переписать все документы одним новым constitution или ничего не менять. Первая создаёт конкурирующий источник правил и риск потери истории; вторая оставляет конкретные semantic escapes. Выбраны local dated clarifications.

**Цена:** несколько поддерживаемых cross-references и необходимость квалифицировать конкретные future producer/consumer paths. Нового product schema, универсального confidence score, taxonomy gate или institution не появляется.

**Проверки будущей реализации:** signed-but-wrong target binding не проходит; valid relation с harmless format change не отказывается; hypothetical value frame доступен как candidate; exploratory winner не выдаётся за подтверждённый результат; changed source вызывает scoped reassessment, а не переписывание прошлого. Эти проверки здесь не запускались.

**Пересмотр:** обнаруженное противоречие с конкретным accepted clause; новый per-domain allowlist; отказ candidate пути только из-за отсутствия protected-positive input; либо дублирующий owner. Если изменение действительно меняет принятое правило, оно выносится из B в отдельное решение, а не называется редакционной правкой.

## C01. Совместный анализ не обязан всегда иметь форму simulation

Точный текст — первый блок [C-target-choices.patch](C-target-choices.patch). Это **новый выбор target wording**, а не утверждение, что так уже решено.

**Рекомендация:** сохранить whole-design joint evaluation; разрешить exact joint derivation или иной валидированный joint witness для именно того свойства, которое он устанавливает. Pairwise checks и сумма individual effects не заменяют joint evaluation. Simulation остаётся основным доступным способом для сложного world model, но сам факт исполнения модели не доказывает эмпирическую истинность.

**Альтернативы:** обязательная simulation при любом дизайне; либо любое приближение считается joint evaluation. Первая бессмысленно исключает точные совместные решения; вторая теряет требуемое свойство. Цена рекомендуемого варианта — property/assumption/version-specific qualification альтернативного witness и его consumers.

**Минимальный discriminator:** совместная нелинейная/constraint interaction, невидимая попарным marginal summaries, должна менять или ограничивать вывод. Exact alternative должен сохранять ту же требуемую property и соответствующие model/assumption refs. Граница разрешения — доказанное свойство, не весь политический claim.

## C02. Несколько обоснованных режимов inference и обучения

Второй блок [C-target-choices.patch](C-target-choices.patch).

**Рекомендация:** Bayesian confirmatory update сохранить как поддерживаемый target. Допустить явно квалифицированные frequentist/sequential, robust и partial-identification profiles там, где они устанавливают требуемое утверждение. Не смешивать posterior, coverage, identified set и no-number procedural claim. W5-K03 diagnosis/admission и применимые profile obligations сохраняются.

**Альтернативы:** Bayesian-only для любого confirmatory знания; либо свободный interchange методов. Первая неоправданно ограничивает типы доступных оснований; вторая подменяет гарантии. Цена рекомендации — отдельная qualification смысла результатов и bridge для каждого метода. Это не поручение реализовать все методы сейчас и не разрешение менять posterior без его собственных входов.

**Минимальный discriminator:** optional stopping под fixed-time interval не сохраняет заявленную гарантию; правильный sequential method не доказывает causal exchangeability; identification interval не подписывается как confidence interval. Успешная диагностика и валидное inference не создают политического мандата.

**Оставшиеся входы:** реальные study/assignment/measurement/target/diagnosis grounds соответствующего случая. Принятие C02 не поставляет их и не меняет чужой institutional scope.

## D. Нужен ли новый документ в SDD

[Связующая записка](proposed/policyos-system-synthesis-and-foundation-lifecycle.md) подготовлена полностью, но после независимой критики **рекомендовано оставить её здесь**. Она помогает увидеть constructive design + knowledge growth + custody как целое, однако почти все обязательства имеют существующих владельцев.

Новый governing SDD сейчас добавил бы цену синхронизации и возможность ссылаться на сокращение вместо исходного решения. Если вы хотите отдельную точку входа в SDD, записку можно перенести после согласования как subordinate explanatory note с точными ссылками и без самостоятельных норм. Действительно новый architecture decision нужен при обнаружении cross-owner contract, который existing documents не выражают, а не просто из-за объёма исследования.

## Применение после решения

Каждый patch подготовлен против исходного среза и проверяется отдельно через read-only applicability check. B и C добавляют текст к одному North Star: их нельзя механически применить вместе без сверки контекста. После выбранного вами набора нужно перечитать текущие файлы, сохранить чужие изменения, скомпоновать согласованные append-only дополнения и записать решение по identity §9.7. До согласования ни patches, ни optional note не переносятся в SDD.

Pattern pass: P05/P10/P13/P15/P20/P25/P27/P32/P35/P36/P37/P38. Capability claims не выдаются; все checks в этом документе — критерии будущего исполнения.
