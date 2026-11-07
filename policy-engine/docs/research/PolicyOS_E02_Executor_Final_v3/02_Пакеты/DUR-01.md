# DUR-01 — Аварийно-устойчивый бюджетный snapshot

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B37. Тип: durability acknowledgment fix + filesystem/recovery qualification.

Доступная запись не получает durable acknowledgment до подтверждённого flush; повтор того же события не списывает бюджет ещё раз и восстанавливает полезную работу после временного сбоя.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/DUR-01.md), [все остатки](../05_Основания/Аудит/01_Реестры/C71_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/DUR-01_исходные_строки.txt), исходный объединённый план §DUR-01 (исторические строки 8313–8386).

## 2. Уже работает — сохранить

- Отдельный стабильный lockfile; strict existing wire и explicit bootstrap.
- Same-directory temp→file fsync→replace→directory fsync; old/new, не blank unlimited.
- Exact event receipt отдельно от bounded journal; legacy record_spend остаётся additive.
- Producer unknown/reuse/attempt attribution и current BudgetMiddleware reload.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C71-R01 | fix: Повтор/resolve должны подтверждать durability, а downstream не повышать readable до committed. | REQ-DUR-01-01 |
| C71-G01 | lifecycle: Поддержанный filesystem/ancestor directory/restore procedure; отказ corruption не заменяет восстановление. | REQ-DUR-01-02 |
| C71-G02 | qualify: Authorized producer→exact settlement→durable ack→budget consumer. | REQ-DUR-01-03 |

### Исходные обязанности, не только новые R

- B37 → REQ-DUR-01-01…-03: atomic publication уже действует; исправить durable ack, квалифицировать supported filesystem и реальное restore без reset расходов.

## 4. Нормативный контракт

### REQ-DUR-01-01
После replace с persistent directory fsync failure settle/replay/resolve spend и producer сохраняют outcome_unknown; readable exact bytes не дают durability=ledger. После восстановления sync тот же event подтверждается с прежней revision/amount без второго charge. Conflicting event identity отказывает.

Источник: B37; аудит: C71-R01; проверки: TEST-DUR-01-01.

### REQ-DUR-01-02
Reader/writer используют стабильный lock; crash оставляет полный old/new либо явное отсутствие первой публикации, не unlimited из existing empty/corrupt. Для заявленного filesystem существует проверенная процедура восстановления из достоверного snapshot/history с сохранением limits, spend, receipts/revisions; неизвестный backup отказывает. Подлинность snapshot недостаточна: authentic-but-stale backup не может уменьшить уже подтверждённый spend/revision или удалить later confirmed receipts. Restore сверяет актуальное authoritative поколение и полный набор подтверждённых receipts; при недоказанной актуальности/reconciliation отказ, не восстановление старого доступного бюджета.

Источник: B37; аудит: C71-G01; проверки: TEST-DUR-01-02.

### REQ-DUR-01-03
Actual authorized producer intent, known/unknown outcome, exact-event settlement и acknowledgment доходят до fresh current budget consumer без дублирования расходов; unknown amount и reuse origin сохраняются, memory-only receipt не получает durable гарантию.

Источник: B37; аудит: C71-G02; проверки: TEST-DUR-01-03.

## 5. Техническое решение и producer → consumer

Обобщить существующий _confirm_compute_durability до private snapshot confirmation under stable exclusive lock, переиспользовать для exact spend/producer replay и resolve_* до возврата durable-meaning результата. Подтверждение: _fsync_dir(parent) + strict readback того же snapshot под lock; OSError или несовпадение → existing BudgetLedgerSettlementOutcomeUnknownError. Не писать отдельный durable=true в тот же несинхронизированный snapshot. Resolve диагностической видимости можно оставить отдельным явно не-durable API только если есть реальный consumer; TracedLLMClient._persist_producer_event должен использовать именно confirmed resolve перед committed/ledger.

Для lifecycle: перечислить фактически поддержанный filesystem и parent directory creation ownership. По существующим backup/recovery источникам выбрать конечный restore path: остановить writers, взять stable lock, валидировать полный authoritative snapshot/receipt identity и его актуальность относительно later confirmed generation/receipts; authentic-but-stale snapshot не имеет права rollback расходов. Только после reconciliation — atomic republish и fresh reload. Если trusted recovery source нет, сохранить отказ и явно потребовать такой источник; не выдумывать ledger из нуля.

### Проверенные owners на срезе
- policy-engine/src/polisyos/scientist/orchestration/engine/budget_ledger.py: _confirm_compute_durability, settle_spend, settle_producer_event, resolve_spend, resolve_producer_event
- policy-engine/src/polisyos/scientist/orchestration/engine/budget_middleware.py: settlement/resolve consumer
- policy-engine/src/polisyos/core/llm/traced_client.py: _persist_producer_event
- policy-engine/src/polisyos/core/artifacts/_atomic_write.py: существующий directory durability ориентир

Новый SQLite/service не нужен; checksum/readback не замена fsync. Флаг в том же файле не подтверждает его durability. Multi-host обещание нельзя получить строкой contract.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-DUR-01-01
- Уровень: unit + targeted native integration.
- Setup: Real ledger/middleware; injected persistent _fsync_dir failure после replace; exact spend и producer; actual acknowledgment methods.
- Действие: First settle→retry/resolve→ack при продолжающемся fault, затем восстановить fsync и повторить same ID.
- Точный oracle: До восстановления unknown и попытка sync при каждом durable confirmation; ack не committed/ledger. После success exact прежний receipt/revision, aggregate charge однажды; conflicting amount/key/provider/digest refusal.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-DUR-01-02
- Уровень: filesystem/process + operational recovery.
- Setup: Supported tmp filesystem, stable lock, concurrent reader/writer; known-good snapshot и corrupted copy, own crash barriers. Дополнительно подлинный snapshot r, после которого подтверждён расход/receipt в r+1.
- Действие: Fault до/после replace, fresh reload; выполнить утверждённый restore под lock.
- Точный oracle: Old/new valid bytes, reader не видит blank; lock inode stable; restored limits/spend/receipts exact known-good, неизвестный backup refusal. Power-loss/multi-host непроверенные гарантии отдельно NOT_RUN. Restore authentic r поверх подтверждённого r+1 отказан либо reconciled с сохранением r+1 spend/receipts; бюджет не увеличен и повтор event не оплачивается заново. Если current generation нельзя установить из доверенного источника, restore остаётся blocked.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-DUR-01-03
- Уровень: native producer integration.
- Setup: Authorized small local producer, typed run/attempt intent, real ledger, no paid external provider.
- Действие: Known failure/cancel/reuse→settlement→fresh budget read; lost ack same-event retry.
- Точный oracle: Actual event provenance/attempt retained; known costs once, unknown not zero; read budget отражает confirmed state; synthetic producer не выдаётся за external billing authority.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/scientist/orchestration/engine/test_budget_ledger_process.py`; `policy-engine/tests/unit/scientist/orchestration/engine/test_budget_ledger_settlement.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: syscall fault injection и own process kill; small local producer. Запрещено: fake ledger/fsync/readback для durability; external billing claims из synthetic event.

## 7. Общая интеграция и порядок

DUR-01 canonical owner exact-event durable settlement; RUN-03 supplies known costs, EXE-01 allows legal read, DUR-02 guards current attempt. Один native integration witness, не новая accounting система.

Точные общие сценарии: E02-I06-C из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: нет обязательного нового предшественника; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Исторические receipt bytes не переписывать для получения guarantee. Existing resolve смысл уточнить через реальный API/consumers; strict legacy read сохраняется. Rollback не может повышать unknown по видимости; при неподдержанном flush отказ остаётся.

## 9. Free-grow и design direction

- policyos-identity-and-custody-boundary.md §1: владеем ровно заявленной гарантией, readable не durable.
- design_direction.md §2.6/§4.7: restore нужен для полезного продолжения; отсутствие trusted source не лечится fabricated budget.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

- DEC-DUR-01-01: release owner объявляет поддержанные filesystem/coordination profiles и trusted recovery source. Выход — исполнимая restore процедура и witness; без источника blocked только restore claim, известный ack fix выполняется.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.

