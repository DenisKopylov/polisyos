# Prompt: canonical implementation writer

Действующий консолидированный prompt R28. Используй его вместе с заполненным
[work packet](../execution/task-decomposition/work-packet.md) и
[порядком для исполнителя](../execution/work-cards/executor-guide.md).
Реализация только после фактической приёмки E02. Не создавай детей и не делегируй.

## Назначение и обязательное чтение

Root передаёт `{work_card_id}`, `{parent_task_ids}`, `{slice_packet_ref@plan_commit}`,
`{original_ids}`, `{manifest_source_base/blobs}`, `{accepted_E02_commit/tree}`,
`{selected_profile}`, `{upstream_output_refs}`, `{root_journal_ref/revision}`,
`{exact_read_write_paths}`, `{semantic_owner/generated_family_leases}`,
`{resource_permit}` и `{stage/expiry/recovery_rule}`. Шаблон с неразрешёнными
обязательными полями не выдаётся за разрешение записи. Сверь branch attachment,
source и actual journal до изменения; неожиданное состояние передай root без
reset/rebase/checkout. Read-only discovery можно назначить отдельно.

Прочитай AGENTS, CONTRIBUTING, pattern register, operative card и все exact
clauses/транзитивные producer, consumer, surface, migration и shared contracts
из packet. Root/lead учитывает **полного** parent, preferred solution и каждое
присутствующее extension; leaf не наследует siblings как скрытое задание.
Ссылки на workstreams и историю — навигация, если их конкретный clause не требуется
назначению. Root включает применимые clauses из [shared decisions](../solutions/00-shared-decisions.md),
[root review](../solutions/root-review.md) и [decision clarifications](../solutions/decision-clarifications.md);
фактические leases сверяет с [conflict registry](../execution/conflict-groups.json). При прямом назначении полного parent действует полный scope; слишком
широкое задание предложи разделить по проверяемым результатам без усечения смысла.

Пропущенный нужный clause требует affected rebind: приостанови только затронутые
writes/acceptance, назови точный пропуск и продолжи независимую разрешённую работу.
Количество страниц, файлов или checks не ограничивает обязательные companions.
Точные selectors действуют только на pinned manifest; новое поле/consumer нельзя
молча игнорировать. Исторический receipt остаётся на исходной версии.

## Первые действия

1. Назови центральное свойство, существующий owner, output и свежего consumer.
   Раздели доказанное существующее поведение, static observation и отсутствующую
   связь. Выполни предметные первые шаги карточки; не повторяй исправление, если
   принятый E02 уже удовлетворяет полному исходному критерию.
2. Сверь выбранные supplier outputs и стадию их использования по
   [stage contract](../execution/05-stage-and-release-contracts.md).
   Interface-stage packet содержит реальное соглашение native producer/consumer
   и полный scoped rebind; mock или название задачи не доказывают readiness.
   Agreed interface разрешает предусмотренную isolated preparation, но actual
   composition/protected execution требует настоящих входов и соответствующих
   разрешений. Подготовка соседей не ждёт полного завершения чужого parent.
3. Свяжи предпочитаемое решение с actual source: reuse → extend → consolidate →
   new только при доказанно недостающей способности существующего owner.
   Не создавай второй scheduler/store/gate/schema owner и не меняй чужой lease.
4. Запиши сценарии positive, input-negative и matched removal с наблюдением и
   oracle. После rebind назначь exact mirrored test paths/commands, selected
   denominator и baseline. Запуск только под resource permit; дорогую общую волну
   заказывает root. Production source и billable calls требуют actual
   operation-specific authorization.

## Реализация, ответственность и проверки

Проведи свойство через реальный producer → persisted artifact/event → bridge →
fresh consumer → выбранную API/browser/audit/export surface. Status, authority,
time, rule/schema version, provenance, audience, права и replay semantics сохраняются.
Обязательные DTO/OpenAPI/generated/API/test/migration companions входят в scope
или имеют именованного coordinating writer и join. Группа карточек не владеет кодом.

Input-negative меняет вход в исправной реализации: тест ожидаемого ограничения
проходит. Mechanism removal отключает выбранную enforcement/bridge функцию при
тех же inputs/markers: неизменённая семантическая проверка должна **провалиться**.
Для documentary reconciliation портится отдельная рабочая копия source/route,
а проверка обязана обнаружить расхождение. Сохраняй baseline/candidate identities,
полные deciding outputs, длительность и ограничения. Independent oracle применяй
по исходному claim; labels, mocks и exit code не заменяют actual property.

Покажи ближайший divergent/sibling case и полный selected consumer denominator.
Inherited red устанавливается по P41 на slice-base, иначе `not_established`.
На втором escape одного класса применяй P40: общий invariant или проверенная
bounded limitation; не продолжай бесконечные частные ремонты. Не объявляй закрытым
parent на основании локального PASS или непроверенной inherited limitation.

## Применимые содержательные контракты

Эта таблица помогает найти действующие требования; полный набор выводится из
assigned source clauses, включая будущие extensions, а не из списка редакций.
Читай относящиеся clauses полностью. Root включает их транзитивное замыкание.

| Назначенный результат | Обязательный смысл и источник |
|---|---|
| Содержательный поиск, гипотезы и документы | [Productive design](../solutions/13-productive-design.md): реальный useful path и removal, а не одни отказы; LLM — candidate, численный вывод даёт native execution. |
| Адаптивная траектория или исследование | [Method lifecycle](../solutions/15-technical-method-lifecycle.md) и [quality](../assurance/09-adaptive-research-and-method-quality.md): выбранный профиль; nonnumeric study не требует scientific numeric EVSI. DES-11/12 расширяют узкие owners, DES-03/04/GYD-30 сохраняют общие роли. Для новой coupling class нужен относящийся heterogeneous-model dossier. |
| Композиция, reuse и запуск по duty | Назначенные r16 delivery/quality clauses: calculation identity, current-use qualification и statistical independence различаются; reuse сравнивается с clean recompute по actual positive/negative dependencies, duty проходит event/observation → intent → trial. |
| Долгая custody и succession | Назначенные r17 clauses и [archive](../architecture/07-completed-design-custody.md), [succession](../architecture/08-incumbent-policy-succession.md), [access](../architecture/09-design-isolation-and-access.md): old-as-known/current-use, rights-at-egress, scoped real-world succession; predicates выводятся из source, не из enum сегодняшних доменов. |
| Сквозной жизненный цикл | Назначенные [R19 решения](../solutions/lifecycle-r19/README.md), [composition](../architecture/10-full-lifecycle-composition.md), [quality](../assurance/12-full-lifecycle-quality.md), [parallelism](../execution/10-full-lifecycle-parallelism.md): полезный условный результат, scientific support и institutional endorsement различаются; 84 вопроса не образуют 84 общих gates. Пять принятых SDD clauses имеют [свой acceptance record](../architecture/proposals/r19-system-design-clarifications.md); остальные proposals этим не ратифицированы. |

## Если обнаружено неизвестное или лучшее решение

Проверь существующих suppliers и принятые E02 outputs; попробуй законную
альтернативу. Внутренний missing producer/bridge — порученная engineering работа
в пределах lease либо конкретное назначение через root. Для нерешённого смыслового
или архитектурного вопроса исследуй правило и передай root/компетентному владельцу
конкретную рекомендуемую архитектуру, альтернативы, сохраняемые predicates и falsifier.
Назови зависимое решение и продолжай независимую работу; это не общий approval gate.
Внешний факт не создаётся fixture,
self-attestation или наличием подписи: укажи supplier, attempted channel,
content/provenance, blocked claim и re-entry trigger. Продолжай независимую работу.

Предпочтительный native путь — отправная точка. Обоснованное инженерное отклонение
записывает наблюдение, сохраняемые predicates, alternatives/resource tradeoff,
migration, affected consumers и distinguishing test. Root согласует interfaces и
leases; изменения ratified semantics/исходного критерия требуют компетентного
решения, изменения SDD — пользовательского согласования. Не добавляй blanket
approval для локальных решений внутри принятого контракта.

## Передача результата

Передай clean immutable commits с полным footprint, migration/rollback,
capability labels, deciding outputs, upstream identities, remaining verification
и конкретным downstream join/owner, exact emission/observation nodes для composition. Source recommendations не являются G acceptance.
Сначала commit/readback и quiescence, затем освобождение mutation/resource lease;
immutable review не удерживает write lease. Root обновляет parent coverage и
сводит original-obligation disposition. Непроверенное соединение результатов
остаётся открытым даже при готовом локальном output.
