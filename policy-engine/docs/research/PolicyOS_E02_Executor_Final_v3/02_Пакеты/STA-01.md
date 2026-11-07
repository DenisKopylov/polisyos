# STA-01 — Изоляция ветвей и точные эффекты replay

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B57, B58, B59. Тип: исправление C61-R01 + сохранение и квалификация существующего механизма.

Полезная исследовательская ветвь должна повторно применяться к текущей основе без потери независимых изменений и evidence keys. Исправить результативный guard protected membership, не изобретать второй patch service.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/STA-01.md), [все остатки](../05_Основания/Аудит/01_Реестры/C61_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/STA-01_исходные_строки.txt), исходный объединённый план §STA-01 (исторические строки 7249–7365).

## 2. Уже работает — сохранить

- Intent journal сохраняет same-value assignment и порядок, различает delete/null/no-write; cached replay использует текущую основу, не старый snapshot.
- Deepcopy только declared mutable subtree с shallow ancestors и alias memo; finite callback-free profile, явный отказ циклам/unsupported objects.
- Существующие NodeCacheEntry schema, mutation/replay proof, исторический checkpoint как целый snapshot. Отказ несовместимому target переводит cache в miss/re-execution, а не успешный частичный hit.
- LK/S для пакета в реестре не назначены; S01–S08 не активируются этим локальным ремонтом.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C61-R01 | fix: Согласовать staged merge с before/after membership; не запрещать полезные добавления и ref updates. | REQ-STA-01-01, REQ-STA-01-02 |
| C61-G01 | qualify: Реальные CAS, restart, worker и failed-node routes ещё требуют supported native evidence. | REQ-STA-01-02, REQ-STA-01-03, REQ-STA-01-04 |
| C61-G02 | shared; owner RUN-03 / DUR-01 / DUR-02: Finite-state replay остаётся здесь; внешние costs/events/actions принимаются их identity/fence owners, не операциями set. | REQ-STA-01-03, REQ-STA-01-05 |

### Исходные обязанности, не только новые R

- B57 → preserve/qualify, REQ-STA-01-02, -04, -05: same-value intent, unrelated preservation, carrier/reader, внешние эффекты и отдельное измерение стоимости.
- B58 → fix/preserve, REQ-STA-01-01, -02: permitted params delete, atomic conflict, protected indices независимо от spelling.
- B59 → preserve/qualify, REQ-STA-01-03, -04: subtree isolation, failed branch rollback, aliases и finite graph.

## 4. Нормативный контракт

### REQ-STA-01-01
При merge операций, затрагивающих inputs, artifacts_index или reports_index, итоговый набор ключей каждого protected root должен содержать все ключи входной текущей основы. Whole-root set, replace и эквивалентные spelling не обходят правило. При нарушении возвращается typed replay/mutation refusal; caller base и committed state не изменяются. Добавление ключа и обновление значения существующего ref разрешены.

Источник: B58; аудит: C61-R01; проверки: TEST-STA-01-01.

### REQ-STA-01-02
При cold, parallel и cache-hit применении journal сохраняются явное y=4 поверх текущего y=9, unrelated=new и отсутствие удалённого независимым шагом поля. В params delete удаляет ключ, null сохраняет ключ со значением null, no-write не меняет его; конфликт parent-delete/child-write не публикует частичный результат.

Источник: B57, B58; аудит: C61-R01, C61-G01; проверки: TEST-STA-01-02, TEST-STA-01-04.

### REQ-STA-01-03
Изменение вложенного list/dict/typed model в declared subtree не наблюдается base и sibling до commit; ошибка/отмена ветви не меняет их. Aliases внутри изолированного subtree сохраняются. Цикл или объект вне finite callback-free профиля явно отказывается до публикации, а не теряет identity.

Источник: B59; аудит: C61-G01, C61-G02; проверки: TEST-STA-01-03, TEST-STA-01-04.

### REQ-STA-01-04
После реального CAS roundtrip и fresh reader сохранённый journal/proof применяется только при совместимых target/epoch/source bindings. Tamper/unsupported historical entry/несовместимый target не дают hit-success; incompatible replay приводит к штатному переисполнению с неизменённой основой.

Источник: B57, B58, B59; аудит: C61-G01; проверки: TEST-STA-01-04.

### REQ-STA-01-05
Replay state не повторяет spend/event/external operation: существующая operation identity и fence остаются решающими. Отчёт об оптимизации указывает измеренные bytes/time/peak memory на объявленном workload, а без измерения не заявляет ускорение или поддержку произвольного Python object graph.

Источник: B57, B59; аудит: C61-G02; проверки: TEST-STA-01-05.

## 5. Техническое решение и producer → consumer

В state_merge.merge_parallel_outcomes уже есть двухфазный сбор/разрешение конфликтов и применение к detached branch. Перед публикацией MergeResult сравнить protected key membership staged результата с текущим base, используя одну узкую общую функцию инварианта с StateMutationGuard, либо эквивалентное сравнение без импорта builtins в низкоуровневый engine. Сравнение только трёх index key sets: не сериализовать весь state ради одного guard. Проверка должна работать и для journal set всего корня, и для unjournaled compatibility route; explicit delete early-refusal оставить. При отказе бросать существующий StateReplayIncompatible на потерянный путь, чтобы executor использовал текущую обработку eviction/re-execution; cold producer guard сохраняет StateMutationViolation boundary. Не возвращать промежуточный staged state.

Producer branch → ordered StateMutationJournal → canonical NodeCacheEntry/CAS → proof-checked reader → _merge_cached_outcome_state → общий merge → consumer следующего узла. Checkpoint остаётся отдельным snapshot restoration, не универсальным patch. Изменение membership guard не требует новой wire schema; если implementation добавит поле proof, назначить version и explicit historical miss.

### Проверенные owners на срезе
- policy-engine/src/polisyos/scientist/orchestration/engine/state_merge.py: merge_parallel_outcomes, _apply_staged_write, _PROTECTED_DELETE_ROOTS
- policy-engine/src/polisyos/scientist/nodes/builtins/guards.py: StateMutationGuard.post_check, _removed_index_paths
- policy-engine/src/polisyos/scientist/orchestration/engine/state_branching.py: branch_state, journal tracking
- policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py: NodeCacheEntry, replay proof, NodeResultCache
- policy-engine/src/polisyos/scientist/orchestration/engine/executor.py: _merge_cached_outcome_state и incompatible replay handling

Не выбирать blacklist только имён операций: он и создал R01. Не запрещать весь protected root set — это ломает корректное обновление ref. Не делать blanket deepcopy всего state или новый replay registry.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-STA-01-01
- Уровень: unit + targeted native integration.
- Setup: Для каждого protected root typed ArtifactRef под evidence; declared/enforced branch. Отдельные допустимые params и ref-update controls.
- Действие: Слить root={} и replacement с потерянным ключом; затем set с сохранённым evidence+new и заменённым ref; повторить cold/parallel/cache routes.
- Точный oracle: Удаляющие варианты typed refusal; исходный evidence тот же и никакой partial commit. Допустимые варианты приняты и consumer видит новый ref/new key. На pinned R01 хотя бы root={} control должен провалиться.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-STA-01-02
- Уровень: unit + targeted native integration.
- Setup: Old state x=2,y=4,unrelated=old; producer явно пишет y=4. Current y=9,unrelated=new, чужое поле уже удалено.
- Действие: Сериализовать journal, replay; отдельно params delete/null/no-write и конфликтующий parent-delete/child-write.
- Точный oracle: y=4,unrelated=new; удалённое чужое поле не воскресает. Три операции различимы по presence/value; конфликт applied=false/typed refusal без изменения base.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-STA-01-03
- Уровень: unit + targeted native integration.
- Setup: params.config с nested rows и двумя aliases одного list; соседняя большая неизменяемая область. Failed node mutate-then-raise.
- Действие: Выполнить реальную ветвь и отказ; проверить base/sibling и alias identity; negative cycle/unsupported callback object.
- Точный oracle: Base/sibling nested value прежнее; branch aliases указывают на один изолированный объект; unrelated не обязана копироваться; неподдержанный граф явно отказан без публикации.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-STA-01-04
- Уровень: native integration P-CORE/P-PROCESS.
- Setup: Изолированные real CAS/index/checkpoint и fresh process; действующий producer, typed NodeOutcome, current-base mutation.
- Действие: Cold execute→cache put→restart→warm read; tamper operation, unknown epoch, wrong target kind; failed-node rollback и process wire.
- Точный oracle: Exact ordered intent и permitted output доступны fresh consumer; invalid proof miss/refusal, incompatible target вызывает ровно штатный recompute, а не частичный hit; protected key invariant общий.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-STA-01-05
- Уровень: cross-owner integration + measurement.
- Setup: Одна operation ID с completed cost/event; выбранный небольшой растущий declared subtree workload.
- Действие: Replay той же ветви через RUN-03/DUR owners; записать размеры и время serialization без искусственного SLA.
- Точный oracle: Чистые assignments применены, spend/event count не увеличен повторно; measurement содержит actual sample/workload/units и не подменяет correctness.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/scientist/orchestration/engine/test_state_merge.py`; `policy-engine/tests/unit/scientist/orchestration/engine/test_engine_executor_idempotency.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: typed small producer и controlled exception/barriers на unit уровне; clock для детерминированного scheduling. Запрещено: fake CAS manifest как доказательство custody, mocked merge/guard, snapshot diff вместо journal, success-shaped worker.

## 7. Общая интеграция и порядок

STA-01 владеет общим protected-membership/replay contract. EXE-02 использует его conflict semantics, RES-01/02 — committed state, RUN-03 — fresh retry branch. Сначала узкий guard и regression, затем joint cold/warm/state scenario; shared process/durable evidence из E02-I06-C переиспользовать, не копировать.

Точные общие сценарии: E02-I06-A, E02-I06-B, E02-I06-C из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: STA-02: cache identity contract; RES-01 / RES-02: checkpoint readers; RUN-03 / DUR-01 / DUR-02: external effects; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Исторические CAS bytes и журналы не переписывать. Старый неподтверждённый snapshot доступен как история, но не как safe patch. Guard repair меняет только ранее ошибочно допустимое удаление evidence keys; допустимые adds/ref replacements остаются. Rollback к версии без guard недопустим для новых writes; при откате code хранить артефакты, отключить affected reuse, безопасно recompute.

## 9. Free-grow и design direction

- design_direction.md §2.6, §4.7–9: durable useful result, история отдельно от current applicability; replay не повышает authority.
- §2.2 и §7 / Vision Rule12 с практической поправкой: один общий membership contract для любого нового node/resource, не if-case ветка.
- CTM §2–5: не вводить универсальную временную оболочку; сохранять native operation/entry semantics.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; хранение не добавляет authority.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

Новых блокирующих продуктовых решений не требуется. Реальную доступность supported runtime установить до native проверки; недоступность оформлять NOT_RUN, не PASS.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.

