# R28: назначение, которое можно исполнить без памяти прежних обсуждений

Документарное уточнение R27 на base `2a07cd8a16bad0191b302f71c699b3bf9082ebac`.
Продуктовая реализация, продуктовые проверки и E02 acceptance здесь не выполняются.
Действующий вход: [executor guide](../execution/work-cards/executor-guide.md),
[writer prompt](../prompts/writer.md) и заполненный [work packet](../execution/task-decomposition/work-packet.md).

## Что было неясно и что исправлено

| Расхождение | Исправление и практический эффект |
|---|---|
| Общая формула positive/removal повторяла заголовок вместо наблюдаемого сценария | Все 38 DEB cards и шесть coordination cards получили предметные первые шаги и конкретный discriminator. Это примеры исполнения полного criterion, а не уменьшенный acceptance. |
| В больших карточках терялись первая проверяемая точка и граница соседнего owner | Уточнены CNT-08 basis/event, GYD-15 receipt, DES-06 document и CNT-05 measure; отдельно OPS-05 restore/retained-use и UI-02 selected placements. Всего первые действия конкретизированы в 52 карточках. Остальные читаются через общий packet с их существующим предметным ядром. |
| OPS-05 acceptance был маршрутизирован по соседней способности | `U012 = task.acceptance_steps[4]` принадлежит restore-cut: S0/withdrawal/reissue/current head. `U013/U014 = [5]/[6]` принадлежат retained-uses: mixed archive и допустимый retained result после raw erasure. UID и source bytes сохранены. |
| Audit-комментарий предлагал исправить уже изменённый маршрут | CNT-04/05/07, CAP-04/05, UI-01/02/04/19 и OPS-05 теперь формулируют работу действующего receiver; coverage и читаемые карточки сверяются вместе. |
| Input-negative и removal допускали противоречивое чтение | Исправная реализация + плохой input даёт ожидаемый refusal. При отключённом механизме одинаковый исходный сценарий должен провалить неизменённую semantic assertion. У documentary reconciliation отдельно названо искажение рабочего evidence/route, не runtime mutation. |
| Последовательные дополнения prompt требовали держать историю редакций | Один консолидированный writer prompt содержит актуальную процедуру, транзитивные требования и ссылки на содержательные контракты. Historical review receipts не превращены в обязательное runtime evidence. |

## Что должен получить исполнитель

Root выдаёт materialized packet с текущим plan commit, immutable source-manifest
pins, принятым E02 source/tree и actual journal/lease revision. Первые шаги карточки
конкретизируются под фактические modules/inputs/commands. Без принятого source
нельзя выдать придуманные пути и команды за проверенное назначение.

Root/lead читает полного parent и сводит исходные обязательства. Leaf читает своё
ядро и все необходимые exact clauses/contract dependencies, включая обязательные
companions. Это уменьшает поиск по всему плану, но не отрезает transitive requirements.
Группа — навигация, не semantic owner; один native writer остаётся владельцем
механизма. Root координирует пересечение exact paths/generated families.

Первый самостоятельный результат — карта фактического owner→output→consumer,
выбранный distinguishing case и понятное следующее действие. Внутреннее отсутствие
bridge — engineering work, не внешний input. Для настоящего внешнего неизвестного
указываются supplier, attempted channel, блокируемый claim и re-entry trigger.
Отсутствие чужого output останавливает только зависимый use/проверку по исходному
stage contract; независимая разрешённая подготовка продолжается.

## Самостоятельное содержательное ревью

- Отказ не подменяет полезный positive: retained result, conditional metric,
  candidate document и supported gross EVSI остаются возможными в своей границе.
- Case examples не перечисляют все допустимые domains/profiles; source criterion
  и actual consumer denominator шире примера. Поддержанная recursive schema сама
  по себе не запрещена. CAP-03 cost нужен для выбранного cost-sensitive use.
- P0-ACCEPT не ждёт нового E02 acceptance от самого себя: читает существующее
  решение G. P0-REBIND может готовить разрешённый census и сводит pins стадийно.
  FINAL-FREEZE не требует будущего replay receipt. Эти исходные стадии не меняются.
- CNT-08 не создаёт новый cascade/status writer; GYD-15 не создаёт второй CAS;
  DES-06 не владеет edit-back или rights; measure-profile не владеет mandate-choice.
- Input/receipt verifier может оставаться включённым в reconciliation corruption.
  В mechanism removal изменение только declaration или ожидаемый отказ из-за
  сломанного setup не считается доказательством. Oracle наблюдает само свойство.
- Количества UID — структурные fragments, не количество всех семантических требований.
  Полный source-bound смысл mixed clauses и parent join остаётся обязательным.

## Независимое чтение и исправления после него

Два независимых reviewer прочитали готовый delta с разных сторон: исполнение
packet/consolidated prompt и сохранение source/owner границ. Исправлены две
конкретные неоднозначности: возвращён явный handoff архитектурной рекомендации
root/компетентному владельцу; составной CNT-05 positive разделён на metric output
и prior-choice history у существующего mandate-choice owner. Primary source
route не перемещён; история уже поручена ему через `task.rollback`.

Root отдельно сверил смыслы negative/removal, условный cost, supported recursive
schema, прогрессивный P0 rebind и freeze→review→replay. Review ограничен этим
изменением и названными source-bound границами, не заявляет новый аудит всего R9.

## Сохранность, проверка и пределы

[Полная документарная проверка](r28-validation.json) проходит весь набор registry,
coverage и source manifests, сверяет UID/selector identity, secondary clauses,
companions, маршруты, stage/owner contracts, читаемые ссылки и три разрешённых
переназначения. Она не является runtime verification или доказательством, что
каждый будущий executor правильно понял смысл. Независимое чтение delta и root
review дополняют структурную сверку; происхождение записано в validation receipt.

Исходные `tasks.json` и `solutions/preferred-solutions.json` не меняются. Сохраняются
262 карточки / 121 parent / 11 групп, исходный task DAG, leases и conditional stages.
Новые product schema/enums/services и изменения SDD не вводятся. Все actual commands,
consumer identities и возможные изменения source после E02 требуют scoped rebind.
Нельзя обещать устранение всех будущих engineering рисков по документации.

Pattern pass: P01/P02 (реальный output/bridge/consumer), P13/P39 (контекст и companions),
P27/P31 (один native owner), P29/P32/P37/P38 (семантический discriminator),
P35/P36 (полный denominator и source identity), P40/P41 (ограничения и provenance red).
Target: понятное назначение с конкретными действиями и проверкой без утраты scope.
Product verification: **UNRUN**; implementation gate: actual E02 G acceptance.
