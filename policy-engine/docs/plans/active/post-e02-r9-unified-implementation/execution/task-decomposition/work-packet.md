# Рабочая карточка: минимальное полное назначение

Этот шаблон материализует [правила R25](README.md). Поля ниже — формат задания
и существующего lease journal, не новый runtime DTO/API или набор product enums.
Не заполнять неизвестные inputs выдуманными defaults. Неразрешённая обязательная
граница препятствует affected dispatch/acceptance по существующим stage rules.

[Порядок R28 для исполнителя](../work-cards/executor-guide.md) объясняет заполнение.
Root выдаёт заполненный packet с действующим operative смыслом. Ссылки на прежние
редакции обеспечивают трассировку, но не заставляют leaf собирать действующее
задание по истории. Unknown source/path можно назначить как read-only discovery;
его неизвестность не разрешает запись и не превращает внутреннюю работу во
внешний input hold.

## 1. Identity и результат

- `parent_task_ids`, `slice_id`, роль (`implementation`, `verification`, `input`,
  `composition review`) и именованный accountable owner родителя.
- Plan commit, actual E02 acceptance, accepted code/tree, selected profile,
  input/contract/rule refs. Stable slice ID не заменяет version binding.
- `manifest_source_base`, точные task/preferred manifest blob/SHA256 и selectors
  из coverage.source_files — отдельно от current `plan_commit`.
- `slice_id` — только identity назначения: он не создаёт canonical task/DAG edge,
  product status или право closure. Для multi-parent packet каждый parent route
  reconciled отдельно; остаток одного родителя не блокирует unrelated работу.
- Одно центральное утверждение о поведении и конкретный observable результат.
- Что означает завершение **этого** slice; какие parent claims он не закрывает.

## 2. Рабочее ядро контекста

Кратко и предметно: что уже существует, точная недостающая связь/свойство,
предпочтительное native решение и почему; producer → artifact/event → bridge →
fresh consumer → permitted surface. Для verification роли — та же цепь,
которую проверяет кампания, без присвоения ей implementation ownership.

Включить все применимые status/authority/time/rights/retention/replay правила,
даже если их реализация у другого владельца. Читатель должен понять обязательство
из ядра и перечисленных normative inputs; не из названия задачи или истории чата.
История отвергнутых вариантов и широкая библиография доступны по точным ссылкам
для углубления. Они не должны скрывать действующее решение.

Указать предметные первые действия и результат каждого: установленный owner,
найденный producer/consumer path, различающий baseline, выбранный input/output
или первый проверяемый checkpoint. Не заменять действия общим «изучи/rebind».
Отдельно назвать, что исполнитель выбирает сам внутри контракта, что потребляет
от supplier, и какое изменение требует решения root/компетентного владельца.
Если одна карточка затрагивает несколько native owners, root назначает существующие
coordinating leases/consumer changes явно; название карточки не создаёт нового owner.

## 3. Coverage и границы

Таблица: `source clause@pin → role in this slice → required input/output/check`.
Роли: исполняется здесь, общее обязательное ограничение, реальный supplier input,
либо передаётся конкретному parent/sibling join. Это не право произвольно пометить
применимое требование out-of-scope. Parent ledger отдельно показывает все остатки.

Не копировать полные tracked sources в каждый packet: приводить точные selectors
и достаточный operative смысл назначенного обязательства. Если поле содержит
несколько самостоятельных требований, разделить их по смыслу и сохранить
общую source ссылку; нельзя считать одно имя поля одним выполненным требованием.

## 4. Входы, lease и параллельность

Для каждого supplier назвать output, owning task, требуемую **стадию** и actual
ref либо agreed interface для preparation. Отдельно completion composition join;
не использовать одну общую dependency list для этих разных отношений.

Указать `root_journal_ref`: точный путь/ref действующего журнала назначений и
его наблюдаемую revision; приложить относящиеся к этому packet lease/dispatch entries.
Шаблон журнала или ссылка на прежний чат не заменяет actual assignment.

Назвать exact read/write paths, semantic-owner и generated-family leases,
mandatory companions, ресурсы и stop/recovery rule. При неизвестном write set
разрешено read-only уточнение, а не конкурирующая реализация. Документация,
проверки, DTO/generated companions не выпадают из assignment ради лимита размера.

## 5. Проверки и handoff

- Полезный positive через реальный native path и свежего consumer.
- Distinguishing negative, включая ближайший sibling consumer/границу.
- Matched removal, при котором markers остаются, а свойство исчезает.
- Полный selected denominator, источники oracle, необходимые compatibility и
  migration cases; фактические проверки только под ресурсным разрешением.
- Конкретный downstream join и его owner; ограничения локального результата.
- Immutable candidate, complete footprint/outputs, review scope, remaining
  obligations и update parent coverage. Публикация slice не равна parent closure.

Для каждой решающей проверки заполнить: source criterion, сценарий/input,
действие, observable/oracle, expected verdict, actual test path/command и стадию
запуска. Input negative и mechanism removal — разные строки: при испорченном
входе исправный consumer ограничивает/отказывает и тест проходит; при отключённом
механизме неизменённый semantic test должен провалиться. Documentary corruption
портит отдельную копию evidence/route при действующем reconciliation. Не требовать,
чтобы отключённый guard сам продолжал защищать свойство. Сценарии — witnesses
полного criterion, не разрешение сузить набор profiles/consumers до примера.

Применимость и стадия quality case отмечаются явно: owner-readiness, selected
composition, финальный replay либо исходный disposition. Включение case в frozen
denominator не означает, что финальный replay уже выполнен до freeze. Роли/стадии
берутся из существующих contracts, не превращаются в новые product enums.

## 6. Проверка перед выдачей

Root отвечает на два вопроса: «сможет ли исполнитель удерживать всё нужное для
этого свойства?» и «где остался каждый кусок исходного обязательства?». Если
ответ требует скрытого знания из старого чата либо чтения всех siblings, packet
переделывается. Если свойство объективно неделимо, сохраняется больший связный
контекст; сокращение путём утраты требований запрещено.

Независимый читатель должен назвать первые действия, output, чужой supplier,
negative/removal и remaining join по выданному packet. Если человек и машинный
route называют разных accountable receivers, исправляются оба представления
перед affected dispatch; исполнитель не выбирает удобную версию сам.

Допустимый перенос: следующий same-writer checkpoint или назначенный successor
получает exact contract/result refs и оставшуюся работу. Не существует требования
уложить capability в заданное число страниц, символов, тестов или commits.
