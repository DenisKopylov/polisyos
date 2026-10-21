# Исполнение выбранных решений без нового круга общих вопросов

Нормативные для этого пакета правила находятся в AD04–06. Этот документ определяет зависимости, минимальную последовательность и проверку полноты. Он не разрешает G research session запускать тяжёлую работу и не заменяет repository gates исполнителя.

## Разделение работы

| Работа | Можно начать | Writer / зависимость |
|---|---|---|
| CAN semantic policy и compatibility/refusal matrix | Сразу | Existing Common/Core/IR owners; один writer на общие readers |
| HTE outcome models, native-profile definition, extractor version split | Сразу | Existing IR HTE + Foundry owners; согласовать единый output-slot ABI |
| B161 typed unknown, basis/observation/relation и current projection | Сразу | Existing Search uncertainty/funnel owner |
| HTE/B161 owned origin and bounded read associations | После фиксации маленьких producer contracts | Existing Runtime/Scientist owner; reuse AD01 intent/fence/projection |
| API/generated/browser/decision-packet migration | После зафиксированного DTO | Один writer публичного owner, consumer census полного затронутого пути |
| Composed acceptance | После consumer migration и independent source review | По frozen source/input/backend; тяжёлый ресурс сериализовать по правилам исполняющего агента |

Три механизма можно проектировать и писать параллельно. Не выдавать общие IR refs/registries, Runtime DTO, generators и lockfile нескольким writers. Отдельная исследовательская группа не нужна: единый локальный оркестратор назначает прямых помощников по фактическим независимым owners.

## Минимальная последовательность

1. Зафиксировать свой текущий attached source/tree и полный фактический consumer footprint. Сопоставить уже написанный код с этими решениями; сохранять полезные реализации и историю. Проверить конкретные новые schema IDs/версии на отсутствие коллизии. Если такая же capability уже появилась у canonical owner, расширить её с явной compatibility mapping вместо дубликата. Это routine engineering, не новый абстрактный G-choice.
2. CAN: закрепить механический profile и contextual reader policy; сохранить raw absence/malformed distinction; устранить семантическое расширение через Core fallback/cache. Сначала readers и честные refusal surfaces, затем writers/companions.
3. HTE: добавить единственный discriminated slot под новым breaking ABI; разделить point capture и inference; selected native profile и origin association; все четыре final producers; новый путь полностью обходит старое CI widening/fallback. Не ждать внешнего population law, чтобы реализовать bounded conditional output.
4. B161: task owner порождает настоящий typed unassessed predecessor для выбранного statistical obligation; method owner сохраняет actual interval/point/assessment; Search recomputes profile и same-basis relation; persist bounded current projection. Старые L0/L3/L4 labels, uninvoked writer и hand-built test observations не заменяют этот путь.
5. Перевести actual current consumers/default selection на новые contracts. Если запуск требует более сильного результата, чем producer может дать, показать именно этот unmet requirement. Не превращать это в исчезнувшую секцию, численный default или generic error.
6. Source freeze → независимое review новых deltas/зависимостей → affected native/installed/public checks и removal → один composed replay. Изменение после freeze требует проверки затронутого delta, а не неограниченного повторения всей системы. Сохранять deciding outputs и точные источники красноты по P41.

## Общий достаточный vertical witness

Один возможный общий путь: обычный versioned observational request (AD03) → fixed method/native backend → exact point/conditional interval outcome (AD04) → CAS reader с нужным facade (AD05) → actual Search first-assessment producer/current projection (AD06) → fresh decision packet/API. Общность пути экономит работу, но не объединяет результаты проверок: каждый контракт имеет свой falsifier и свой scope.

Отдельно нужен point-only HTE путь. Он не даёт статистическую interval-based оценку B161; current native point виден, inference и routing score остаются unavailable. Положительный interval witness не может подменить этот случай.

Матрица учёта включает: producer call, output/persistence, owned origin/fence, content/profile/target verification, actual consumer, публичную проекцию, installation/generated companions, adversarial/removal. Нельзя свести строку к наличию модели или constructor test. Mapping всех новых и старых default aliases обязателен; поведение historical replay показывается отдельно.

## Правила для заранее ожидаемых затруднений

- **Нет native interval:** закончить point-only outcome/consumer, сохранить конкретную причину. Не изобретать CI и не прекращать весь slice.
- **Есть interval, но нет population guarantee:** разрешён только точно названный conditional result с limitation. Не называть API `PopulationSummaryResults` доказательством population inference.
- **Поддерживаемая версия backend не установлена:** контракт/readers можно закончить; native результат UNRUN с точным requested profile. Доступность backend проверяет исполняющий агент штатным путём, без притворного PASS.
- **Native error:** различать известное отсутствие протокола и реальную ошибку. Сохранённый independently validated point можно показать как limited; повреждённый fit/target не спасать числом.
- **B161 требует новый input или L3→L4 changing profile:** новая basis epoch/отдельная проекция; не выдавать за выбранное same-basis first assessment. Candidate exploration продолжается. Для actual assessed→assessed изменения подготовить конкретный method-valid relation, если он нужен исходному consumer.
- **Нет law для routing score:** AD06 уже выбирает явную ограниченную convention. Нужны actual source values и воспроизводимый computation, не разрешение внешней организации. Нельзя применять её к authority или статистической coverage.
- **Нет issuer/custody/live currentness:** не подделывать. As-of candidate result остаётся возможным при законном доступе; live/authority claim сохраняет limitation.
- **Нужен CAN universal tag registry:** выбранный контракт его не требует. Сначала expected reader/schema и existing contextual policies. Новая общая grammar оправдана лишь конкретным продуктовым consumer, которого выбранный bounded контракт принципиально не может обслужить.
- **Legacy artifact/ref:** сохранить старое значение и source qualification. Новая семантика требует нового artifact/view/ABI; удобный metadata overlay не превращает старое выполнение в новое.
- **Дешёвый proxy вместо проверяемого свойства:** назвать divergence и расширить canonical invariant один раз; не строить лестницу marker checks. Повторный пример уже объявленного bounded residual не повод бесконечно переделывать механизм.
- **Падает unrelated gate:** следовать P41 с exact slice base и полным input denominator; если provenance красноты не установлен, так и записать. Не bypass hooks и не объявлять заочно inherited.

## Когда возвращаться к G

Возвращать только точный конфликт: выбранное решение, фактический owner/consumer, минимальный counterexample, рассмотренные reuse/extend варианты, рекомендуемый delta, миграция и decisive falsifier. Обычный codec, serializer, version registration, invoke/wire, absence/null, cache key, current projection, dependency inventory или default migration исполнитель решает сам по данным правилам.

Общий stop не требуется, пока остаётся независимая разрешённая работа. Недоступные external inputs записывать адресно: кто может их произвести, exact required scope/format, какие claim/consumer они блокируют и что уже работает без них. Прежде чем назвать input внешним, проверить, не является ли он вычислимым внутренним output или отсутствующим bridge.

## Handoff обратно G

Разделить архитектурное соответствие, accepted code, passed bounded checks, finding recommendations и formal closure. Предоставить immutable commits/trees, actual producer/consumer footprint, selected inputs/profile/backend, полные deciding outputs, removals и remaining limitations. Не переносить green ранних HTE/CAN receipts на новый source; не закрывать B31/B161/LA-021 только номером этого решения. Не трогать исторический B198. `main` требует отдельной авторизации.

Pattern pass: P01/P02/P03/P04/P05/P07/P08/P10/P27/P28/P29/P31/P32/P35/P37/P38/P40/P41. Acceptance основан на actual paths и различающих вмешательствах; этот план не является runtime receipt.
