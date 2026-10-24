# LIF-02: пример меньших назначений R25

Форма: `sequence`. Это проект границ будущей выдачи, не implementation grant или новая приёмка. Основа — R24 `f8e2c66edf6b56a5436e696e669bfe690f68e58b` и корректировки R25; реализация только после E02 acceptance.

[Правила декомпозиции](../README.md) · [Формат рабочего пакета](../work-packet.md) · [Канонический task](../../../tasks.json) · [Preferred solution](../../../solutions/02-custody.md#LIF-02)

## Почему такая граница

Keep one claim-currentness/enrollment writer. Separate native ordered-event replay from bounded observation cuts, then add the R24 conditional duty composition witness after shared interfaces are ready. The stages have different evidence bases and consumers but share the currentness owner and do not add start edges.

## Общие условия родителя

Названные ниже свойства сохраняют все применимые original criteria, extensions, status/authority/time/rights и mandatory companions. Root/lead перед назначением раскладывает **каждый** source clause в существующий coverage journal; этот пример не заменяет такую раскладку. Один actual semantic owner и write lease сохраняются. Независимая подготовка возможна по согласованному интерфейсу; composition и protected use требуют настоящих supplier outputs.

План не даёт права выбирать только удобные profiles или считать unknown applicability исключением. Условный join включается по фактическому контракту/claim. Родитель требует полный selected denominator и fresh end-to-end witness; локальные PASS не суммируются в closure.

## native_event_replay — Enroll and replay source-native events

**Свойство.** No event is missed between evaluation cut C and enrollment high-water W; current publication is fenced by the enrolled source/right cut and expected claim head.

**Граница и owner.** LIF-02 is the sole semantic currentness/enrollment/head owner under write:claim-currentness; ledger persistence and the publisher commit fence participate within that lease, not as peer semantic writers. CAP and source owners emit cuts/events.

**Входы.** Qualified native source cut, journal identity/incarnation, replay floor, enrolled dependency and expected claim head.

**Результат.** Durable enrollment, replayed invalidation history, processed position and current or bounded-cutoff result.

**Подготовка.** Rebind exact source generation and transaction/reconcile contract; preserve coarse stale-before-fanout behavior.

**Composition join.** Replay event-before-enrollment and concurrent source/right change through a fresh claim and publisher reader with scheduler stopped.

**Полезный positive.** A new matching record invalidates a dependent negative/set claim; unrelated generations remain usable.

**Различающий negative.** Missing replay floor, dedupe-before-effect crash, backdated event, or concurrent change before public commit. Ledger and publisher participation cannot be split into incompatible currentness contracts.

**Matched removal.** Remove C-to-W replay but keep dedupe markers, or remove writer-participating fence but keep a green projection; fresh reader must fail.

## bounded_observation_order — Consume bounded observations with honest as-of scope

**Свойство.** Local observation receipts support only declared observed coverage; completion order or byte equality cannot establish source continuity or clear a newer mismatch.

**Граница и owner.** LIF-02 remains currentness writer; CAP-04 supplies observation receipts and CAP-02 the exact representation.

**Входы.** Exact root/profile/selector/coverage and observation interval plus local attempt/head/journal identity.

**Результат.** Scoped observed/as-of currentness or limitation, with conflicting/stale replies retained as evidence.

**Подготовка.** Bind observation cut and expected head; separately consume qualified own-assessment changes without inventing a webhook/event.

**Composition join.** Deliver poll A after B has observed a changed root/coverage loss; test A-to-B-to-A and read affected/unaffected claims.

**Полезный positive.** A supported observation changes only enrolled dependent uses; qualified assessment drift can change its dependent currentness without a webhook.

**Различающий negative.** Identical later bytes, partial polls, missing local replay floor, later local journal position, or no-feed status claimed as uninterrupted source currentness. Unqualified metrics and unadmitted derivative-only variance must not stale the parent claim; an admitted correction must not leave its enrolled dependent claim green.

**Matched removal.** Remove observation-cut/head binding while retaining journal markers; delayed A clears B or reader emits unjustified current green. Separately remove qualified-assessment-to-enrolled-premise binding: a dependent fresh read remains falsely green after admitted drift. Remove the derivative-only guard: unadmitted variance wrongly downgrades the parent.

## conditional_duty_join — Compose selected duty outcome into claim currentness

**Свойство.** A missed or limited continuing custody promise changes only enrolled dependent coverage, and wrong/missing duty relation cannot bypass the join.

**Граница и owner.** LIF-02 is the consumer; LIF-04 is the duty producer, with OPS-11 and LIF-06/OPS-08 joined only for their asserted guarantees.

**Входы.** Native claim-duty relation and coverage contract plus actual due/continuation/cutoff/lapse and conditional supplier outputs.

**Результат.** Fresh claim/history/API state reflecting overdue, continued, transferred, cut off or limited coverage.

**Подготовка.** Agree the scoped interface and allow owner readiness in parallel; no whole-task start prerequisite.

**Composition join.** Miss the actual committed interval, including an outage with no overdue event, whether a heartbeat is still visible or absent; use durable due/continuation and enrollment evidence, then read affected and independent claims through the selected fresh UI-02/UI-19/API consumer. No unconditional dependency on every UI reader.

**Полезный positive.** Affected coverage becomes limited/overdue before compute/review completes; independent claim continues; reconciled continuation restores only supported use.

**Различающий negative.** Wrong duty/scope, omitted required relation, queue marker without actual effect, outage crossing due without any emitted overdue event, or resource/service guarantee without its supplier output. Missing heartbeat is not evidence of continued coverage.

**Matched removal.** Remove durable due/enrollment reaction or due-outcome-to-claim/surface bridge while queue and review markers remain; the affected-versus-independent fresh readers must detect false currentness even when no overdue event was emitted.

## Явные inherited routes, которые нельзя потерять

- `R18-D03-Q03` и `R18-D22-Q03` → bounded_observation_order: positive для
  qualified own-assessment/admitted correction, negative для unqualified
  metric/derivative-only variance, отдельные removal controls обеих сторон.
  Genuine CAP-04 source events проходят native_event_replay; watcher не добавляется.
- `R18-D16-Q01/Q02` → conditional_duty_join: пропущенный/неоценимый due во время
  outage ограничивает только зависимые enrolled claims, даже без overdue event.
  Candidate/unrelated работа продолжается. Сохранён selected R24 duty relation
  и реальный fresh surface join; labels/heartbeat не заменяют effect.

Это важные distinguishing routes, не полный перечисленный denominator родителя.

## Что надо материализовать после E02

Exact candidate/tree и contract pins; полный clause-to-result route; accepted supplier refs; actual read/write/semantic/generated leases; native implementation and consumer paths; полные deciding outputs и parent integration witness. Пока это неизвестно, чтение/подготовка продолжаются, affected implementation/acceptance не выдаётся под выдуманный default.

Новая substantive clause требует delta review затронутого контекста; неизменные siblings не перечитывают весь пакет. Смена исполнителя получает явный checkpoint, действующий контракт и остаток — не память предыдущего чата.

Pattern pass: P01/P02/P13/P27/P29/P35/P37/P38/P39. Все проверки выше — будущие acceptance signals; runtime execution UNRUN.
