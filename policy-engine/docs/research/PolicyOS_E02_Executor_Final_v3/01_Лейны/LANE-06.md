# LANE-06 — Состояние, исполнение, восстановление, CAS и миграции

**Статус: EXECUTOR_SPEC_NOT_IMPLEMENTED. Все будущие проверки NOT_RUN.** Основание: commit `20d9009be21097bfbdc38a546a15cc60213b8ace`; завершённый аудит не равен завершённому ремонту. 22 пакета, 75 нормативных REQ и 75 локальных test contracts. Технический исполнитель и независимый reviewer назначаются проектом.

## Точный состав
- [STA-01](../02_Пакеты/STA-01.md) · [JSON](../04_Трассировка/STA-01.json)
- [STA-02](../02_Пакеты/STA-02.md) · [JSON](../04_Трассировка/STA-02.json)
- [EXE-01](../02_Пакеты/EXE-01.md) · [JSON](../04_Трассировка/EXE-01.json)
- [EXE-02](../02_Пакеты/EXE-02.md) · [JSON](../04_Трассировка/EXE-02.json)
- [RES-01](../02_Пакеты/RES-01.md) · [JSON](../04_Трассировка/RES-01.json)
- [RES-02](../02_Пакеты/RES-02.md) · [JSON](../04_Трассировка/RES-02.json)
- [RES-03](../02_Пакеты/RES-03.md) · [JSON](../04_Трассировка/RES-03.json)
- [RUN-01](../02_Пакеты/RUN-01.md) · [JSON](../04_Трассировка/RUN-01.json)
- [RUN-02](../02_Пакеты/RUN-02.md) · [JSON](../04_Трассировка/RUN-02.json)
- [RUN-03](../02_Пакеты/RUN-03.md) · [JSON](../04_Трассировка/RUN-03.json)
- [DUR-01](../02_Пакеты/DUR-01.md) · [JSON](../04_Трассировка/DUR-01.json)
- [DUR-02](../02_Пакеты/DUR-02.md) · [JSON](../04_Трассировка/DUR-02.json)
- [WIRE-01](../02_Пакеты/WIRE-01.md) · [JSON](../04_Трассировка/WIRE-01.json)
- [CAS-01](../02_Пакеты/CAS-01.md) · [JSON](../04_Трассировка/CAS-01.json)
- [CAS-02](../02_Пакеты/CAS-02.md) · [JSON](../04_Трассировка/CAS-02.json)
- [CAS-03](../02_Пакеты/CAS-03.md) · [JSON](../04_Трассировка/CAS-03.json)
- [REP-01](../02_Пакеты/REP-01.md) · [JSON](../04_Трассировка/REP-01.json)
- [CAN-01](../02_Пакеты/CAN-01.md) · [JSON](../04_Трассировка/CAN-01.json)
- [MIG-01](../02_Пакеты/MIG-01.md) · [JSON](../04_Трассировка/MIG-01.json)
- [MIG-02](../02_Пакеты/MIG-02.md) · [JSON](../04_Трассировка/MIG-02.json)
- [MIG-04](../02_Пакеты/MIG-04.md) · [JSON](../04_Трассировка/MIG-04.json)
- [MIG-05](../02_Пакеты/MIG-05.md) · [JSON](../04_Трассировка/MIG-05.json)

## Порядок и общие owners

1. **State/cache:** STA-01 staged result membership и journal invariants → STA-02 current ParameterTransfer/cold-warm → EXE-02 dependency/admission ordering. EXE-01 исправляет общий nonblocking completion bridge; тот же `common/async_tools/__init__.py` затрагивает RUN-01. Эти изменения интегрировать последовательно, не создавать два executor.
2. **Checkpoint:** RES-01 sufficient-state/double-resume → RES-02 ok-only frontier/atomic tier → RES-03 actual same-leaf partial persistence. REP-01 подключает CLI/direct Scientist owner к тому же fresh-head сценарию. Работающий predecessor удовлетворяет dependency без нового product patch.
3. **Process/budget/durable:** RUN-01 deadline/context → RUN-02 real EOF/process lifecycle → RUN-03 cancellation known-cost/attempt classification; WIRE-01 typed task/receipt boundaries проверяются в этом же process пути. DUR-01 durability confirmation обеспечивает reuse spend/producer records; DUR-02 heartbeat/fencing/continuation использует настоящие ledger/checkpoint owners, не новое хранилище.
4. **CAS:** CAS-01 immutable selected views и custody дают общий fixture seed; CAS-02 generation transfer/безопасное сохранение previous output → CAS-03 snapshot/signature и cancellable inventory. Общие `store.py`, `_transfer_ops.py`, `_signature_ops.py` и ownership boundaries интегрировать последовательно. Конфигурируемая signature policy сохраняется: допустимый unsigned профиль не становится запрещённым.
5. **Canon/migrations:** CAN-01 сохраняет separate Core/IR policies и intentional conformance delta. MIG-05 shared linear mechanism/strict callback registration поддерживает MIG-01/02/04, но Common и IR profiles не сливаются. MIG-01 — единственный owner C79-R01 в `tools/lib/fs.py`; MIG-02/04 только потребляют исправленный `_dump` и shared fault evidence. Единственный ops runner уже существует; retired root parser не восстанавливать.

Пакеты `MIG-01/02/04` делят `tools/ops_runners/migrations/migrate.py` и operational bindings. CAS, retry, async bridge, state/checkpoint файлы имеют cross-packet read-contract impacts даже там, где исходный static write mutex отсутствовал. Reserve actual files/commit перед patch; не менять тестируемый worktree во время job.

## Единственная общая интеграция

Канонический контракт: [LANE-06 shared scenarios](../03_Интеграция/LANE-06.md). Не копировать тяжёлый harness в22 карточки.

| Сценарий | Producer → persistence → fresh consumer | Различающий результат |
|---|---|---|
| E02-I06-A | cold producer → cache/journal → warm current-state merge | Protected deletion отказана, no-write/same-value/null различены; current ParameterTransfer достигает consumer; dependency launches после committed predecessor. |
| E02-I06-B | completed tier/partial sibling → checkpoint/head → fresh resume/CLI | Completed узел не повторён, remaining исполняется; late same-leaf result не потерян; replay check-only не запускает backend. |
| E02-I06-C | typed real process attempt → budget/durable records → takeover/continuation | EOF не маскируется compute timeout; known cost не потерян; stale owner не публикует; продолжение выполняет только remaining work. |
| E02-I06-D | selected CAS views A/B → exact transfer → signature/fresh CAS reader | Один content blob не теряет provenance views; failed export сохраняет A/foreign files; configured custody и cancellation/completeness честны. |
| E02-I06-E | supported historical/current payload → canonical converter/CLI → родной reader | Original bytes/identity сохранены; validated/unchanged/converted/admitted различены; historical aliases не обходят conformance authority gate. |

CP2 — окно связанной приёмки, не новый runtime registry и не обязательный полный CI после каждого файла. Общий installed-package результат переиспользуется с packaging owner (CP6), не заменяя локальные negative regressions.

## Положительные способности, которые нельзя закрыть одним запуском старых тестов

- STA-02: current invocation ParameterTransfer должен попасть в downstream manual/hybrid path; reused selector сам по себе недостаточен.
- RES-03: известные пригодные результаты текущего leaf должны переживать поздний сбой и достигать fresh reader; если фактический route этого не умеет, нужен узкий общий projection/partial-result контракт.
- RUN-03: outcome/cost cancellation классифицируются по фактическому receipt; нельзя удовлетвориться старым ошибочным expected cost.
- DUR-02: reconciliation должно приводить к полезному remaining-work continuation под тем же budget/operation identity, не только к остановке stale worker.
- CAS-03: cooperative stop должен прерывать census/dedup loops, а не только admission после их завершения.

Для каждого bounded investigation в карточке заданы варианты, критерий и обязательный выход. Если capability отсутствует, требуется общий минимальный repair либо честный unresolved статус; не пересчитать G как PASS от imports.

## Профили, ограничения и evidence

P-CORE: Python >=3.14,<3.15 и project lock. P-PROCESS: реальные собственные subprocess, pipes, process groups, temporary DB/CAS; Linux и Darwin — отдельные evidence, не взаимозаменяемые mock PASS. P-PACKAGING: isolated installed import/registered entry с согласованным packaging owner. Dependencies не устанавливать без разрешения.

Допустимы controlled clocks/barriers/fsync failures и маленькие synthetic inputs. Финальное native evidence не может подменять actual CAS custody, budget ledger, model validator, crypto, process transport или fresh reader именно там, где они являются предметом проверки. Existing fixtures расширяются, но fixture-only evidence маркируется отдельно. Метрики latency/RSS/throughput — измерения с profile/denominator, не вывод из bounded queue counters.

Для каждого принятого patch предъявить base/patch SHA, actual caller map, REQ→TEST→command/log/exit, failing old-mechanism control, useful positive consumer outcome и preservation evidence. В JSON точно связаны67 residual records,69 remaining obligations и105 preservation obligations; shared C79-R01 не размножен в новые defect IDs. Это проверка полноты документов, не выполнение75 тестов.

## Совместимость и design direction

[Identity/custody §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md) и [Custody-time §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md): content identity, историческая подлинность, текущая пригодность, authorization и semantic validity имеют разные основания. Полезный candidate/partial результат допускается без фиктивной authority. Физический layout этих документов не догма.

Free-grow: один branch/journal механизм, один shared executor, один immutable CAS writer, один schema-neutral migration engine и существующие domain owners. Новый совместимый ресурс подключается через общий контракт; новые семантические свойства требуют обоснованного общего расширения, не специальной ветки под каждый тест. Исторические counts/PASS остаются в sealed audit. Полные probes доставлены отдельно в phase1 ZIP; этот комплект не переписывает аудит и не мигрирует пользовательские данные.

