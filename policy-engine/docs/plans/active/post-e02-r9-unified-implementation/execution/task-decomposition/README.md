# R25: размер задачи и контекст исполнителя

R26 материализовала этот подход: [рабочие карточки и логические группы](../work-cards/README.md), [короткий обзор](../work-cards/overview.md). R25 audit/proposals сохраняются как история анализа; актуальные назначения выбираются из текущих карточек R28 и перепривязываются к принятому E02. [Порядок для исполнителя](../work-cards/executor-guide.md) раскрывает первые действия и проверяемую передачу результата.

Это организация будущего исполнения, не новая продуктовая архитектура.
Реализация остаётся после фактической приёмки E02. Исходные task IDs, критерии,
dependencies и статусы сохраняются в [tasks.json](../../tasks.json).

**Разделять следует самостоятельные проверяемые результаты, а не страницы
текста.** Родительская задача хранит полный договор о capability; рабочая
карточка назначает исполнителю обозримый срез этого договора. Несколько рабочих
карточек не создают несколько владельцев одного инварианта.

## Какую проблему обнаружил разбор

Task/preferred manifests смешивают несколько полезных функций: исходный критерий,
техническое решение, cross-owner composition, исторические уточнения и полный
verification denominator. В prompts накопилось требование читать все extensions
и их ссылки для целой задачи. Это правильно для проверки полноты родителя, но
может перегрузить leaf, которому назначен один из его механизмов.

Длина — только сигнал для рассмотрения. Две копии одного criterion в task и
preferred solution увеличивают текст, не число обязанностей. Короткая карточка
может скрывать большой scope за ссылкой. Ни лимит символов, ни число файлов,
checks или commits сами по себе не являются критерием правильного разделения.

## Три разных действия

| Disposition | Когда подходит | Что выдаётся исполнителю |
|---|---|---|
| `retain` | Один связный механизм/исходный criterion; основные части нужны одновременно | Одна рабочая карточка без дублирующей истории; все необходимые semantic clauses и companions |
| `sequence` | Один изменяемый инвариант/owner, но работу можно продолжать через проверенные checkpoints | Последовательные назначения на совместимых bases; интерфейс, migration и связанные проверки остаются вместе |
| `split` | Различимые observable результаты с реальной owner/interface/stage границей и независимо проверяемым смыслом | Несколько slices с named input/output и отдельный parent composition/coverage join |

Это рекомендации по форме назначения, не product status enums. `split` не
означает concurrent writes; `sequence` не запрещает параллельную подготовку
consumer/oracle. Один файл, schema family или semantic owner сохраняет одну
write lease. Номера slices не задают порядок: фактические stage edges и conflicts
выводятся после rebind. Для некоторых больших verification/release родителей
естественны отдельные property campaigns и aggregate decision, а не новый код.

## Родитель и рабочая карточка

Родитель сохраняет исходные IDs, весь scope и конечную ответственность за
композицию. Его нельзя объявить завершённым по сумме зелёных leaf reports.
Нужны complete obligation coverage, реальные producer outputs, fresh consumers,
selected surfaces и все исходные условия disposition/release.

Leaf получает [work packet](work-packet.md): одно центральное свойство, exact
basis, включённые требования, границы, upstream interfaces/artifacts, допустимые
writes и результаты. Обязательные DTO/API/generated/test/migration companions
входят в это же назначение либо получают явного coordinating writer с join.
Деление «сначала schema, потом когда-нибудь producer и тесты» не создаёт capability.
Interface-only preparation допустима как таковая, без product completion claim.

**Необходимый контекст не становится необязательным от того, что он длинный.**
Если замыкание требований всё ещё не помещается в обозримое назначение, root
выбирает более узкий проверяемый результат, последовательные checkpoints либо
сохраняет неделимый scope. Механическое сокращение содержания запрещено.

## Кто обеспечивает полноту

Root/назначенный lead сначала рассматривает полный parent task, preferred
solution, каждое присутствующее `*_extension`, referenced delivery/quality
clauses, исходные criteria и актуальные решения. Для **каждого обязательства**
фиксирует маршрут: конкретный slice; общая binding clause выбранных slices;
parent composition witness; либо явный ещё не назначенный остаток. Последний
блокирует соответствующую полноту родителя, но не независимое готовое назначение.

Shared binding clause — ограничение, не доказательство выполненного obligation.
Каждый substantive route имеет accountable owner, требуемый output/evidence и
parent join либо pinned prior disposition/обоснованную conditional границу,
external/human wait или явный unallocated остаток. Один coverage marker не
подменяет фактическое производство и потребление.

Conditional scope выводится из native contract/выбранного claim и подтверждённого
основания, не из желания уменьшить карточку. Unknown applicability не означает
«не относится». Исторически закрытое или доказанно эквивалентное обязательство
имеет source-qualified disposition, а не исчезает из denominator.

Для packet assignment это правило имеет приоритет над прежними широкими
указаниями prompts читать task/workstream/preferred solution/extension/family
целиком: обязательны exact assigned clauses и их необходимое замыкание. При
прямом назначении целого parent сохраняется полное чтение.

Leaf читает полностью **свой** packet и его транзитивно необходимые clauses:
shared invariants, consumed contracts, generated/surface/migration consequences.
Весь родитель и история остаются доступны как навигация, но не принудительное
задание реализовать всех siblings. Если обнаружен пропуск, leaf передаёт точный
counterexample root; affected scope уточняется, самостоятельная работа идёт дальше.
Leaf приостанавливает только affected writes/acceptance до уточнения scope и
leases; незатронутая работа продолжается. Ни короткая карточка, ни summary автора
не отменяют canonical AGENTS/CONTRIBUTING.

Coverage хранится в существующем task/lease journal; отдельный tracker/service
не нужен. Используйте stable original/question/clause IDs, а где их нет — exact
file@plan-commit и однозначный field/section selector. Selector внутри массива
действителен только для pinned version. Summary не является source obligation.
Семантические atoms определяет review, а не число JSON leaves или строк.

## Что нельзя разрезать без совместного witness

- Единую authority/status/currentness boundary на несвязанные producer и emitter
  с разными трактовками. Допустима параллельная работа, но один contract owner
  и обязательный actual end-to-end join.
- Shared physical budget на независимые квоты slices; attempts на независимые
  observations; recovery на «backup успешен» и «reader запускается» без consistency.
- Один public DTO/generated family на ручные клиентские patches разных writers.
- Closed original criterion на переименованные новые задачи или множество
  тестовых карточек, которые будут ошибочно суммироваться как capabilities.

## Изменения контекста и повторный dispatch

Packet связывает plan commit, accepted source, contract/profile и upstream refs.
Изменение источника требует semantic delta review затронутого requirement/consumer
closure; простое равенство parent ID недостаточно. Новое поле/extension не
игнорируется. Незатронутые назначения продолжаются после подтверждения их basis.
Старый receipt остаётся на своём pin; branch history не переписывается.

`sequence` checkpoints также содержат полный действующий контракт и remaining
obligations; новый исполнитель не наследует память предыдущего чата. Shared
invariants могут включаться в несколько packets как ограничения, но новый код
механизма пишется один раз и потребляется через canonical interface.

## Как проверять качество декомпозиции

1. Независимый reviewer объясняет свойство, producer/consumer, запрещённое
   поведение и acceptance только по packet и его обязательным точным inputs.
   Если для этого надо перечитать всё семейство, граница не достигла цели.
2. Удалить substantive clause из покрытия — parent completeness не проходит;
   незнакомый extension не исчезает. Удалить только историю обсуждения — свойство
   и его coverage сохраняются.
3. Два slices пытаются писать один owner или заменить supplier своим stub —
   конфликт/ложная composition готовность обнаруживаются.
4. Все локальные checks прошли, но свежий consumer получает несовместимый output —
   parent join остаётся незавершённым. Сумма leaf PASS не заменяет эту проверку.
5. Взять новое native method/source/profile: decomposition следует его actual
   properties и contracts, без постоянного нового owner или фиксированного
   перечня технологий. Предложения этого аудита не являются exhaustive taxonomy.

Это documentary procedure probes для будущего исполнения, не запущенные tests.
Число рабочих slices и достигнутая concurrency уточняются по принятому E02,
реальным write sets и ресурсам; никаких performance обещаний из подсчёта карточек.

## Материалы разбора

- [Полный аудит задач](audit.json) — recommendation/rationale для каждого parent.
- [Предложения по семействам](proposals.md) — конкретные границы меньших работ.
- [Результат review и пределы](../../assurance/r25-card-audit.md).

Предложения ещё не являются ready-to-dispatch grants: перед назначением требуется
complete clause allocation, accepted-source rebind и exact leases. Они позволяют
сделать такое назначение предметно, сохранив parent obligation ledger.

Pattern pass: P01/P02/P03/P13/P27/P29/P31/P35/P37/P38/P39/P40.
Главные риски — выдать маленькую schema за capability, уронить sibling consumer,
удвоить owner, спутать площадь текста со сложностью и потерять часть критерия
при сокращении. Product implementation/verification — UNRUN до E02 acceptance.
