# Получение оснований, повторное использование и развёртывание

Итоговая исследовательская редакция R9, 2026-10-21. Продолжение [жизненного цикла](11-foundation-lifecycle.md), не production runbook, принятый ADR или подтверждение deploy readiness. Код, инфраструктура и system-design-decisions этой работой не меняются. Runtime probes — UNRUN.

**Рекомендуемый путь — постепенно наращиваемая библиотека версий и способов получения поверх существующих owners.** Предварительная подготовка, поиск во время задачи и непрерывное наблюдение за изменениями используют общие capture/verification/use границы. Различаются инициатор, бюджет, срок и требуемая полнота. Данные, полученные во время задачи, обычно стоит сохранять, если это разрешено и полезно; сохраняется точная версия с происхождением, а не бессрочное право использовать её в любом следующем выводе.

## Что именно проектируется

1. [Каналы и маршруты получения](acquisition/01-acquisition-routes.md): web/LLM, файлы, APIs, SQL, streams, удалённое вычисление, научные и институциональные входы; предварительная подготовка, runtime и updates.
2. [Содержательное покрытие и право](acquisition/02-foundation-and-legal-routes.md): все текущие 26 семейств атласа, подробный юридический маршрут и составной пример.
3. [Хранение, продвижение и повторное использование](acquisition/03-storage-and-reuse.md): конкретные зоны/owners, runtime→библиотека, private/shared copies, restricted/query-only sources, retention и migration.
4. [Развёртывание и доступ](acquisition/04-deployment-and-access.md): локальный, серверный, гибридный и облачный варианты; реальные конфигурационные seams, ограничения backend parity, ресурсы и интерфейсы.
5. [Реализация и проверка](acquisition/05-implementation-and-review.md): вертикальные поставки, протокол commissioning, adversarial review и оставшиеся решения.
6. [Эксплуатация, доверие и передача custody](acquisition/06-operational-continuity.md): trust bootstrap, ресурсы внешних поставщиков, смена хранителя, commissioning и прекращение currentness promises.
7. [Текущий receipt](research-receipt-r9.json) и [предыдущий](research-receipt-r8.json): documentary scope и проверки. Source maps остаются в [карте reuse](lifecycle/01-reuse-map.md).

## Принятые для этого проекта рекомендации

| Решение | Смысл для реализации |
|---|---|
| Общая capture/use граница для preseed и runtime | Background task также оставляет source identity, durable receipt, semantic bounds и последующий use admission. Runtime находка не становится второсортным временным файлом. |
| Одна логическая библиотека, несколько физических областей | Общие identity/relations, но разные tenant/cell/rights/region/retention boundaries. Не единый мировой bucket и не копирование каждого входа в каждый run. |
| Разделять capture, discovery и допустимость применения | Exact bytes могут быть сохранены, но ещё не доступны поиску другого principal; обнаруживаемая запись может оставаться candidate; admission действует для выбранного use. |
| Сначала metadata, затем необходимая materialization | Получать достаточный для решения slice; не выдавать его за полный источник. Для неизвестных потребностей поддерживать независимый discovery/contrary-evidence поток. |
| Remote compute — отдельный проверяемый маршрут | При запрете переноса raw делать разрешённую работу у custodian. Возвращённый aggregate/receipt тоже требует права, source binding и проверки; credentials не передаются LLM. |
| Фактическая deployment capability важнее имени backend | FS/S3/GCS/queue/Kubernetes не взаимозаменяемы по custody, locking, bounded reads и restore. Нужен conformance evidence для выбранной комбинации. |
| Расширение в основном данными и profiles | Новый source поддержанного класса — configuration; новый transport/parser — локальный adapter; новая causal/legal/measurement семантика — reviewed owner extension, а не prompt. |

## Как читать итоговую версию

Сначала этот индекс и [очередь A0–A7](acquisition/05-implementation-and-review.md), затем документы нужного маршрута. [Lifecycle/05](lifecycle/05-implementation-protocols.md) — canonical переходы и consistency; [lifecycle/09](lifecycle/09-resource-execution-design.md) — resource execution; acquisition/01–04 — конкретизация каналов, содержания, размещения и доступа; acquisition/06 — операционные handoffs. Карта кода закрепляет статический срез, а receipts — историю исследований. Они не переопределяют текущий проект и не доказывают соответствие движущегося E02 candidate.

**Статус назначается точной цепочке, а не всему документу.** Проект без admitted chain и назначенного owner — `absent/unallocated`; существующие, но не соединённые endpoints — `bridge_missing`; `verification_missing` применим только после wiring, `semantic_test_missing` — при прошедших structural checks и отсутствующей semantic проверке. Документированные contracts не всегда `contract_only`: нужен настоящий contract artifact. `UNRUN` характеризует исполнение проверки, а не наличие реализации. Не понижать реально существующий компонент до absent и не повышать prose до implementation. Точные локальные findings @C остаются ограниченными прочитанным путём.

R9 закрывает пробелы **проекта** по concurrent cursor commit, HTTP representation/redirect, trust succession, cumulative disclosure, adaptive inference, человеческим свидетельствам и передаче custody. Это не закрытие product findings. Новые семейства не нужны: уточнены связи и жизненные циклы имеющихся оснований. Free-grow означает configuration/данные для поддержанного класса и локальное owner extension для новой семантики, без центрального switch по семействам.

## Связь с целью PolicyOS

Система учится лучше искать, получать и использовать основания, расширяя причинную модель мира. Разрешено исследовать альтернативные definitions, laws, metrics, priors и scenarios для одного policy task. Каждый вариант сохраняет свои assumptions, obligations и scope; сравнение не стирает несовместимость единиц, популяций, правовых режимов или ценностных выборов. Изменение выбора основания является изменением программы обоснования, а не только refresh кэша.

Критерий полезности acquisition: уменьшился конкретный пробел либо открылась новая обоснованная возможность/контргипотеза. Скачанный терабайт, найденная citation или заполненный каталог сами по себе этого не доказывают. Получение внешнего акта остаётся внешним институциональным действием; PolicyOS организует запрос и проверяет свидетельство, но не подписывает его за учреждение.

Standing опирается на S0-K03/S0-K06/S0-K14 и CTM native owners: собственное действие получения и публикации требует соответствующего основания; candidate исследования могут продолжаться с честно названным unknown. Документы не вводят новые product enums. [C03](sdd-proposals/lifecycle-c03-20261021.md) остаётся отдельным ранее подготовленным предложением на согласовании. Новый обязательный SDD для описанных маршрутов не требуется: это детализация уже выбранной identity/custody/free-grow позиции. Изменение этих принципов потребовало бы отдельного согласования.

Pattern pass: P01/P02/P12 — explicit producer→artifact→bridge→consumer; P05/P15 — LLM и storage не authority; P07/P08 — source cut и use time; P14/P25/P35 — search coverage и independence; P27/P31 — reuse; P32/P37/P38 — real admission; P39/P40 — конечные вертикальные механизмы. Все новые end-to-end свойства требуют проверки; текст не является formal closure E02.
