# RES-01 — Повторный resume, достаточный state и дешёвый индекс

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B63, B70, B71. Тип: preserve/qualify; новые product changes только по воспроизведению.

Два последовательных resume продолжают ту же задачу без повторных A/B и без требования ненужных cache refs; первое полезное продолжение доступно реальному reader.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/RES-01.md), [все остатки](../05_Основания/Аудит/01_Реестры/C65_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/RES-01_исходные_строки.txt), исходный объединённый план §RES-01 (исторические строки 7666–7785).

## 2. Уже работает — сохранить

- Immutable origin fingerprint отдельно от residual workflow; functional change refused.
- Exact successful-ref memo (ID/kind/media/profile), failed load не memoized, eviction/discard invalidate.
- State/typed artifact availability вместо count cache refs; allow_replay реально запускает полный original plan.
- Полный completed reopen не требует removed-node registry. LK/S дополнительных нет.

Изменение продукта требуется только при воспроизведённом несоответствии ниже; отсутствие native проверки само по себе не дефект. Не создавать искусственный рефакторинг для отчёта.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C65-G01 | qualify: Actual CAS/lock/head/history/runner/fresh process вместо storage fixtures. | REQ-RES-01-01, REQ-RES-01-02, REQ-RES-01-03 |
| C65-G02 | qualify: Dedupe принят как механизм; tail только если measurement доказывает пользу и history binding сохранён. | REQ-RES-01-04 |
| C65-G03 | capability: Конечный census actual residual consumers/declarations и согласование grammar; отсутствующее чтение нельзя закрыть простым test run. | REQ-RES-01-03 |

### Исходные обязанности, не только новые R

- B63 → REQ-RES-01-02/-04: exact dedupe реализован; измерить реальный I/O, не старую v1 модель entry+outcome=2reads.
- B70 → REQ-RES-01-01: native double resume, changed functional input, completed reopen.
- B71 → REQ-RES-01-03: достаточные реальные входы остатка, meaningful null/grammar/declarations; full replay только явно.

## 4. Нормативный контракт

### REQ-RES-01-01
A→B→C с остановом после A и после B возобновляется исходным workflow: каждая invocation исполняется один раз, origin fingerprint неизменён, residual fingerprints отражают B→C/C. Functional parameter/dependency change отказывает, operational timeout-only change не меняет functional fingerprint; completed reopen возвращает durable state без нового node lookup.

Источник: B70; аудит: C65-G01; проверки: TEST-RES-01-01.

### REQ-RES-01-02
При восстановлении одного cache owner exact successful ref читается для admission один раз через trace+checkpoint; different selected profile/ref одного key проверяется отдельно, conflict не подменяет first accepted. Failed load retry разрешён, eviction/discard очищает memo. Scope/proof/corruption guards выполняются и при actual get.

Источник: B63; аудит: C65-G01; проверки: TEST-RES-01-02.

### REQ-RES-01-03
Resume проверяет реальные required reads остатка, typed external ArtifactRef verify+read и declared grammar, а не количество refs. Полное valid state без cache seed продолжается; missing required input отказывает либо при explicit allow_replay возвращает original plan с degraded reason. Actual supported consumer с незаявленным read/nullable/list contract должен получить исправленную декларацию/общий accessor либо явное ограничение до acceptance.

Источник: B71; аудит: C65-G01, C65-G03; проверки: TEST-RES-01-03.

### REQ-RES-01-04
Qualification report содержит calls/bytes/time-to-first-useful-result для duplicate-heavy и distinct-ref workload на real backend. Если tail optimisation выбран, offset привязан к подтверждённым run/attempt/history/head; потеря/подмена хвоста не даёт accepted continuation. Без доказанной выгоды достаточно текущего full scan с честным измерением.

Источник: B63; аудит: C65-G02; проверки: TEST-RES-01-04.

## 5. Техническое решение и producer → consumer

Существующие checkpoint.resume_from_checkpoint, compute_workflow_fingerprint, _missing_completed_state_paths и NodeResultCache.load_entry уже решают основную задачу. Не добавлять второй resume service. Перенести bounded A/B/C witness в real tmp store/lock/head/history/local runner и два fresh processes, считая durable invocation identities, не memory counters.

Для G03 выписать state_reads/state_writes всех nodes выбранного residual workflow и сравнить с фактическими inputs consumer tests. _state_path_available сейчас поддерживает model/dict и non-null, не list segment. Если ни один supported reader не требует list/null, явно сохранить этот finite contract. Если требует — расширить общий существующий accessor с container-aware semantics, согласовав STA-02/EXE-02, и различающим test. Не считать похожий JSON ссылкой.

G02: instrument existing read calls без замены backend. Tail не обязательный новый код: сначала сравнить recovery expense с полезной работой; решение и результаты добавить в текущий owner README.

### Проверенные owners на срезе
- policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py: resume_from_checkpoint, compute_workflow_fingerprint, _state_path_available, _missing_completed_state_paths
- policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py: _cache_ref_identity, load_entry, seed_from_trace/entry_refs
- policy-engine/src/polisyos/scientist/orchestration/engine/runner/local_runner.py: LocalWorkflowRunner

Не отключать fingerprint/scope/verify, не count refs, не suppress current read checks ради speed. Нельзя объявлять allow_replay working при передаче residual plan.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-RES-01-01
- Уровень: native persistence integration.
- Setup: Tmp protected CAS, A/B/C actual nodes, original functional spec, stop barriers на durable checkpoints.
- Действие: Cold A→stop; fresh resume B→stop; fresh resume C; completed reopen; functional change negative.
- Точный oracle: Calls a=b=c=1 durable identities; final values/refs равны uninterrupted control; origin stable, residual distinct; changed input WorkflowMismatchError; reopen no new producer/lookup.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-RES-01-02
- Уровень: unit + targeted native integration.
- Setup: Real v2 entries A/B, 100 copies A из trace+checkpoint; failed transient read, profile mismatch, same-key different ref; LRU1.
- Действие: Seed same owner, get, eviction/reseed.
- Точный oracle: Два unique admission reads для A/B; get отдельно проверяет usable entry; failed attempt не memoized; changed profile прочитан/validated, conflict keeps first; LRU forces read again.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-RES-01-03
- Уровень: unit + targeted native integration.
- Setup: Completed A/B, residual C reads params.b и typed ref; full state/no seeds, duplicate A refs/missing b, missing/corrupt/denied blob; selected consumer declaration inventory.
- Действие: Strict resume и explicit allow_replay; grammar/null controls по реальным callers.
- Точный oracle: Full valid state идёт C; duplicate refs не закрывают b; unavailable ref refused; replay executes A,B,C с reason. Supported declarations покрывают каждый actual read; unknown grammar не false available.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-RES-01-04
- Уровень: measurement + optional regression.
- Setup: Два объявленных workloads, real current backend; existing full scan baseline.
- Действие: Measure bytes/calls/time и optional bound tail при обоснованном решении.
- Точный oracle: Таблица воспроизводимых значений без SLA; same accepted index/result. Tampered run/attempt/head tail refusal; без tail честно сохранить full-scan scope.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_res_01.py`; `policy-engine/tests/unit/scientist/orchestration/engine/test_checkpoint.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: малые deterministic nodes и transient I/O fault; counters только observation. Запрещено: fake runner/lock/head/store для double-resume acceptance, JSON-ref substitution.

## 7. Общая интеграция и порядок

RES-01 владеет resume identity/sufficiency и recovery memo; RES-02 — atomic frontier; STA-01/02 — journal/source proof. Один E02-I06-B double-restart witness покрывает совместимые REQ, не отдельные копии тяжёлой инфраструктуры.

Точные общие сценарии: E02-I06-B из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: STA-02; RES-02; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Origin fallback к прежнему workflow_fingerprint остаётся лишь в существующей schema-compatible области; исторические bytes не менять. Старый status-unestablished checkpoint не становится current valid. Rollback сохраняет историю/refs и требует safe refusal для неподтверждённого continuation.

## 9. Free-grow и design direction

- policy-design-execution-topology.md §6: replay сохраняет actual inputs/decisions, не обещает одинаковые токены.
- design_direction.md §2.6/§4.7–9: durable полезность и historical/current distinction; оптимизация не ослабляет custody.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). История и текущая пригодность раздельны; физическая раскладка не догма.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

- DEC-RES-01-01: actual consumer census определяет поддержку list/null grammar. Выход до acceptance — finite table path/type/null semantics + tests; не объявлять arbitrary JSON graph поддержанным.
- DEC-RES-01-02: tail выбирается только по measurement; отсутствие tail не дефект при выполненном exact-dedupe контракте.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.

