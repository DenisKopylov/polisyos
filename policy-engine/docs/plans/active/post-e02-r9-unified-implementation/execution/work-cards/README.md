# R26: рабочие карточки по способностям системы

Это основной навигатор будущих назначений после R25. Реализация начинается
только после фактической приёмки E02. Карточки уточняют работу, но не выдают
resource/authority/write grants и не объявляют capability принятой.

[Короткий обзор и количества](overview.md) · [Машинная карта](registry.json) ·
[Маршруты исходных требований](coverage.json) ·
[Проверка декомпозиции](../../assurance/r26-grouping-review.md).

## Три уровня без трёх параллельных планов

1. **Родитель** в [tasks.json](../../tasks.json) сохраняет original IDs, полный
   критерий, preferred solution, все extensions, зависимости и final disposition.
   Эти 121 родитель не прибавляются к числу рабочих карточек.
2. **Рабочая карточка** назначает один observable результат или честно обозначенный
   coordination checkpoint. У неё один primary group, один parent и один ID.
   Другие группы потребляют её результат по ссылке, а не заводят копию.
3. **Группа** объясняет место работы в способности системы. Она не владеет кодом,
   не является новым модулем/сервисом, не назначает authority и не задаёт очередь
   «закончить всю группу, затем начать следующую».

Machine registry — карта документации и маршрутизации, не второй task tracker.
Фактические назначения, exact leases, source pins и прогресс ведутся в существующем
root journal. Счётчик карточек не является лимитом free-grow или обещанием числа
одновременно работающих исполнителей.

## Как исполнителю начать работу

Root выбирает нужную карточку, сверяет её source parent и выдаёт materialized
[work packet R25](../task-decomposition/work-packet.md). Читать всю группу или
всех siblings не требуется. Обязательны operative card, её точные source clauses,
транзитивно необходимые contracts и применимые repository instructions.

UID в coverage — указатель на точный source fragment в pinned task/preferred
manifest. Это не новый finding и не утверждение «один UID = одно требование».
Если fragment содержит несколько самостоятельных обязанностей, accountable
receiver обязан собрать названные supplier outputs и проверить весь fragment.
Нельзя выбрать только его удобную часть. `clause_uses` явно назначает подрезультаты составного fragment другим карточкам; это не второй primary route и не двойной счёт требования. Индексы массивов применимы только
к указанной версии; изменение источника вызывает affected rebind.

Identity, source/debt references, исходные owners/leases и stage/activation rules
сохраняются отдельно как inherited parent contract. Они не потеряны из-за того,
что не повторены в prose каждой карточки. Linked normative documents читаются
по относящимся к назначению clauses; один JSON-fragment census не доказывает
полноту этих транзитивных требований.

Перед writes после E02 нужно разрешить actual native paths, semantic owner,
generated family, read/write sets, upstream versions и resource permit. Ранняя
карточка не доказывает, что эти будущие write sets не пересекаются. У неизвестной
границы остаётся read-only preparation, а не спекулятивная реализация.

## Ownership и соединение результатов

Один механизм/инвариант имеет одного canonical writer. Разные карточки одного
writer могут продолжать его работу на последовательных совместимых bases;
независимая подготовка, inputs и oracles могут идти параллельно. Consumer card
не переписывает supplier ради удобства и не меняет его contract без согласования.
`kind=input` описывает порученную работу с входом: это не назначение внешнего
issuer, компетенции, law или права доступа.

Parent join называет **конкретные outputs карточек и fresh consumer**. Это
ответственность root/lead за composition, не невидимая дополнительная реализация.
Если join требует отсутствующего producer/bridge/reader, работа назначается
именованной карточке либо остаётся явно unallocated; нельзя скрывать её словами
«интегратор соединит». Shared binding constraint не является исполненным output.

Ни aggregate join, ни сумма leaf PASS не закрывают original criterion без его
полного actual witness. P0/FINAL остаются явно обозначенными coordination cards:
они собирают работу многих исполнителей, а не обещают узкую реализацию одному.

## Зависимости имеют разные смыслы

- `dependency_routes` показывает, какая карточка потребляет output уже имеющегося
  parent supplier. Stage разрешается из [stage requirements](../stage-requirements.json):
  supplier invariant → per-edge override → parent dependency stage — для direct relations. Acceptance/conditional/execution relations сохраняют отдельный source selector, условие и стадию; interface_reference не является новым gate.
- `after_cards` — только необходимая внутренняя preparation зависимость, не
  порядок по номеру и не право обойти parent prerequisite.
- `joins_cards` — потенциальные именованные composition links с `join_conditions`.
  Список не означает unconditional all-of: actual input обязателен только для
  выбранного исходного свойства и указанного условия. Это не стартовая блокировка
  независимой подготовки; альтернативные event/observation или optional EVSI не
  превращаются в обязательную общую цепь.
- `acceptance_dependencies`, conditional composition, execution permissions и
  selected profile rules остаются binding. Их нельзя потерять, сведя всё к
  списку `depends_on` или карте групп.

E02 acceptance остаётся общей входной границей. P0 может выпускать полностью
сверенный disjoint scope, пока продолжает общий census; complete P0 reconciliation
нужно до FINAL-FREEZE. Selected final verification campaigns входят в один
FINAL-REPLAY на принятой identity, а не запускают по replay на каждую карточку.

## Как проверена и где ограничена полнота

Структурная проверка разворачивает все UID ranges, сопоставляет точные selectors,
проверяет один accountable route на fragment, все parent IDs и source edges,
одну primary group на карточку, отсутствие потерянных/несуществующих ссылок и
внутренних preparation cycles. Отдельный substantive review проверяет свойства,
полезные outputs, actual consumers, owner conflicts и размер semantic closure.
Структурная зелень не заменяет этот review.

Обязательные falsifiers: удалить source clause; сослаться на отсутствующего
supplier; назначить два writers одному смыслу; выдать весь parent через один
скрытый read link; превратить composition join в start gate; принять локальные
PASS без actual fresh consumer. Эти ошибки должны быть видимы в routes/leases
и в review, а не теряться за новым красивым названием.

При новой source/version/contract delta пересматриваются affected карточки и
их joins. Исторический результат остаётся на своём pin; counts этой редакции —
описание текущей карты, не постоянная таксономия capabilities. System-design-decisions
и продуктовый код здесь не меняются.

Pattern pass: P01/P02/P03/P13/P27/P29/P31/P35/P37/P38/P39/P40.
Target: полный source scope, один owner, меньший operative context и проверяемое
место каждого результата в общей цепочке. Product execution — UNRUN.
