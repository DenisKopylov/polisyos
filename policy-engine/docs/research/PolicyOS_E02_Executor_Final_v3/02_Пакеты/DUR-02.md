# DUR-02 — Поколение worker и безопасный backend handover

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B38, B78. Тип: heartbeat lifecycle fix + native fencing + reconciled handover capability.

Старый worker теряет возможность продолжать cooperative работу и current writes; неопределённый primary исход разрешается сверкой, а не слепым повтором.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/DUR-02.md), [все остатки](../05_Основания/Аудит/01_Реестры/C72_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/DUR-02_исходные_строки.txt), исходный объединённый план §DUR-02 (исторические строки 8387–8488).

## 2. Уже работает — сохранить

- Owner/attempt/running/valid lease SQL fences и affected rows.
- Atomic status/progress/event/outbox, повторная commit admission и legitimate same-transaction renewal.
- Typed pre-dispatch authority/BLOCK, identity-bound health witness.
- Post-dispatch outcome_unknown без local replay; diagnostic CAS можно сохранить без current attachment.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C72-R01 | fix: Окончательная остановка heartbeat должна выставить existing lost signal. | REQ-DUR-02-01 |
| C72-G01 | qualify: Actual initialized store/process/takeover/outbox/scoped CAS, PostgreSQL отдельно. | REQ-DUR-02-02 |
| C72-G02 | capability: Safe outcome_unknown не завершает handover; нужен bounded reconciliation→remaining work путь existing owners. | REQ-DUR-02-03 |

### Исходные обязанности, не только новые R

- B38 → REQ-DUR-02-01/-02: heartbeat interruption + actual stale/current transaction/custody.
- B78 → REQ-DUR-02-03: pre-dispatch policy и positive reconciled continuation после lost reply; существующий safe refusal не продуктовый дефект.

## 4. Нормативный контракт

### REQ-DUR-02-01
Если heartbeat прекращает renewal из-за typed store timeout/unavailable, existing JobExecutionInterrupt.lost устанавливается до выхода pulse; следующий cooperative guard прерывает handler. Если выбрана bounded retry политика, она обязана завершиться до известного lease expiry и также сигналить при невозможности подтверждения. SQL fencing остаётся независимым обязательным guard.

Источник: B38; аудит: C72-R01; проверки: TEST-DUR-02-01.

### REQ-DUR-02-02
Stale A после expiry/takeover не меняет current B running/completed через complete/fail/progress/sibling mutation inlet. Current B и подтверждённое same-attempt renewal работают. Event/commit fault откатывает status/progress/history/outbox вместе; diagnostic CAS A остаётся читаемым в разрешённом scope, но не current result B.

Источник: B38; аудит: C72-G01; проверки: TEST-DUR-02-02.

### REQ-DUR-02-03
Healthy primary выполняется один раз; pre-dispatch unavailable запускает local только при typed permission, BLOCK/access/contract failure не дают нового права. После effect+lost reply нет blind local: existing operation/checkpoint/owner evidence сверяет completed frontier, отзывает старое current admission и продолжает только недоделанное с прежним operation ID и общими deadline/budget; при неоднозначности остаётся outcome_unknown.

Источник: B78; аудит: C72-G02; проверки: TEST-DUR-02-03.

## 5. Техническое решение и producer → consumer

Минимальный R01 — interrupt.lost.set() в typed dependency exception перед окончательным return _lease_pulse; также проверить stop branch, чтобы shutdown не оставлял дальнейший guarded handler допустимым. Не изменять unrelated worker/class signals. Более сложный retry не нужен без измеренного требования availability.

G02 bounded wiring: у fallback_runner после PrimaryExecutionOutcomeUnknownError не добавлять catch→local. В существующем higher runner/checkpoint owner добавить явный reconcile/resume путь, получающий primary operation ID, last admitted attempt/fence и подтверждённые artifacts/frontier. Сверка через actual store + RES-01 origin contract; доказанная завершённая операция возвращает её результат, доказанный остаток передаётся local под новым current lease но прежней logical operation identity. Неустановленный внешний эффект остаётся blocked; человеку/owner отдаётся точный требуемый evidence. Один пригодный local deterministic case достаточен для механизма, не универсальность backend recovery.

### Проверенные owners на срезе
- policy-engine/src/polisyos/runtime/http/services/control_worker.py: _run_with_lease_heartbeat / _lease_pulse
- policy-engine/src/polisyos/runtime/http/services/control_plane_store.py: _resolve_job_execution_fence, _job_fence_where, _require_fenced_write, transaction admission
- policy-engine/src/polisyos/scientist/orchestration/engine/runner/fallback_runner.py: typed pre-dispatch decision, PrimaryExecutionOutcomeUnknownError
- policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py: resume_from_checkpoint

Cooperative signal не заменяет SQL fence; новый journal/случайный retry UUID не создают exactly-once. Не расширять backend authority по network message.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-DUR-02-01
- Уровень: unit + targeted native integration.
- Setup: Actual worker/guard, renew=False, typed unavailable/timeout, unrelated worker positive.
- Действие: Stop pulse and invoke guard; join heartbeat.
- Точный oracle: Lost set и handler interrupted для окончательного renewal отказа; unrelated worker продолжает; no stale current write при реальном store. Heartbeat не оставляет бесконечный permitted state.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-DUR-02-02
- Уровень: native process persistence.
- Setup: Actual initialized SQLite store/CAS; A held, lease expiry B takeover; injected event and commit faults.
- Действие: A пытается все protected/sibling writes; B completes; same-attempt renew positive; fresh scoped reads.
- Точный oracle: A affected rows0/typed refusal, B exact current result; faults rollback всех связанных rows/outbox; diagnostic A bytes retained but unattached. PostgreSQL отдельно при заявленной поддержке.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-DUR-02-03
- Уровень: cross-owner reconciliation integration.
- Setup: Primary actual local test effect journal с operation ID и real checkpoint; lost response; explicit fallback permissions; remaining node.
- Действие: Run unknown→reconcile→resume; ambiguous evidence and access/BLOCK controls.
- Точный oracle: Effect count1; completed refs reused, only remaining runs; common budget/deadline not reset, old fence can't commit. Ambiguous remains unknown, no local effect; permitted pre-dispatch local positive once.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_dur_02.py`; `policy-engine/tests/unit/remediation/test_dur_02_process.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: typed store failure для signal unit и controlled lost response; own effect fixture не платёж. Запрещено: fixture SQL schema/outbox как native custody PASS, fake health witness, external act authority.

## 7. Общая интеграция и порядок

DUR-02 owns fencing/handover; RES-01 checkpoint origin/readback, DUR-01 exact cost, RUN-01 deadline. Не делать DUR-02 обязательным входом простого local run без fallback.

Точные общие сценарии: E02-I06-C, E02-I06-B из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: RUN-03; RES-02; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Safe current unknown behavior сохраняется; reconcile — explicit дополнительный путь, не silent fallback. Existing artifacts/history не удалять при lost lease. Legacy ALLOW не может расширить typed BLOCK.

## 9. Free-grow и design direction

- policy-design-execution-topology.md §3–6: failure превращается в обоснованное продолжение, не слепой повтор.
- policyos-identity-and-custody-boundary.md §3–6: external effect принадлежит его owner; PolicyOS хранит доказанную связь, не присваивает exactly-once.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

- DEC-DUR-02-01: выбрать один поддержанный primary/local pair и operation evidence для reconciliation. Выход — real completed/remaining/ambiguous table и positive continuation witness. Внешний непримиримый effect блокирует только соответствующее продолжение.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.

