# R25: где уменьшить размер назначения

Разобраны все **121 canonical task** и их 121 preferred-solution row. По смыслу обязанностей: **48 split / 40 sequence / 33 retain**. Это рекомендации по организации будущей работы, а не измерение качества памяти модели и не автоматическая смена task graph.

Полные rationale и предлагаемые property/owner boundaries для каждой строки — в [audit.json](audit.json). Рабочий leaf не обязан читать весь этот каталог: root выбирает нужную границу и материализует [work packet](work-packet.md). Исходный parent сохраняет complete coverage и composition acceptance.

## Начать с этих примеров

| Parent | Рекомендуемая выдача | Что остаётся общим |
|---|---|---|
| [LIF-02](examples/LIF-02.md) | Native event/enrollment; bounded observations; selected duty-to-claim join — checkpoints одного writer | Claim-currentness owner, order/fence semantics и fresh publisher |
| [GYD-30](examples/GYD-30.md) | Compiler/joint result; selected temporal/cyclic recovery; actual Foundry reuse consumer | Один совместный результат; reuse owner LIF-07, temporal adapter DES-11 |
| [OPS-05](examples/OPS-05.md) | Directional migration; restore consistency; verified bytes-to-consumer | Native stores, rights/history и единая eligibility восстановленного чтения |
| [DES-10](examples/DES-10.md) | Productive alternatives; transfer; numerical/reexecution; document fidelity; reader comprehension | Frozen basis, costs/exposure, selected scope и общая итоговая проверка |
| [UI-02](examples/UI-02.md) | Exact publication across audiences; pre-egress privacy; reader consumption of retention decisions | Единый record, actual audience rights; LIF-05 остаётся retention owner |

Пять примеров раскрывают input/output, ownership, preparation/composition и positive/negative/removal. Это не полные runnable assignments: exact source binding и полный clause allocation выполняются после приёмки E02. Раннее фиксирование будущих file leases без actual source добавило бы ложную точность.

## Полный маршрут по семействам

В таблицах `split` требует нескольких observable результатов, `sequence` сохраняет одного writer и передаёт работу через checkpoints, `retain` сохраняет цельный scope. Конкретная concurrency определяется реальными writes и supplier stages. Ни номера, ни число slices не добавляют start dependencies.

### CAP — получение и custody

| Рекомендация | Task IDs |
|---|---|
| `split` | `CAP-01`, `CAP-02`, `CAP-03`, `CAP-04`, `CAP-06` |
| `sequence` | `CAP-05` |
| `retain` | — |

### LIF — жизненный цикл оснований

| Рекомендация | Task IDs |
|---|---|
| `split` | `LIF-01`, `LIF-04`, `LIF-05`, `LIF-06` |
| `sequence` | `LIF-02`, `LIF-07`, `LIF-08`, `LIF-09` |
| `retain` | `LIF-03` |

### GY — native mechanisms

| Рекомендация | Task IDs |
|---|---|
| `split` | `GYD-01`, `GYD-12`, `GYD-15`, `GYD-20`, `GYD-22`, `GYD-24`, `GYD-27`, `GYD-28`, `GYD-29`, `GYD-30`, `GYD-32`, `GYD-33` |
| `sequence` | `GYD-02`, `GYD-03`, `GYD-06`, `GYD-07`, `GYD-09`, `GYD-10`, `GYD-11`, `GYD-16`, `GYD-17`, `GYD-19`, `GYD-21`, `GYD-31` |
| `retain` | `GYD-04`, `GYD-05`, `GYD-08`, `GYD-13`, `GYD-14`, `GYD-18`, `GYD-23`, `GYD-25`, `GYD-26` |

### Atlas — surfaces

| Рекомендация | Task IDs |
|---|---|
| `split` | `UI-02`, `UI-15`, `UI-17` |
| `sequence` | `UI-01`, `UI-04`, `UI-06`, `UI-08`, `UI-10`, `UI-12`, `UI-13`, `UI-18`, `UI-19` |
| `retain` | `UI-03`, `UI-05`, `UI-07`, `UI-09`, `UI-11`, `UI-14`, `UI-16`, `UI-20` |

### CNT/DES — основания и содержательный дизайн

| Рекомендация | Task IDs |
|---|---|
| `split` | `CNT-05`, `CNT-06`, `CNT-07`, `DES-04`, `DES-10`, `DES-12` |
| `sequence` | `CNT-01`, `CNT-04`, `CNT-08`, `DES-03`, `DES-07`, `DES-09`, `DES-11` |
| `retain` | `CNT-02`, `CNT-03`, `CNT-09`, `DES-01`, `DES-02`, `DES-05`, `DES-06`, `DES-08` |

### OPS — deployment и ресурсы

| Рекомендация | Task IDs |
|---|---|
| `split` | `OPS-05`, `OPS-06`, `OPS-07`, `OPS-08`, `OPS-09`, `OPS-10`, `OPS-11`, `OPS-12` |
| `sequence` | `OPS-01`, `OPS-02`, `OPS-04` |
| `retain` | `OPS-03` |

### Долги и aggregate acceptance

| Рекомендация | Task IDs |
|---|---|
| `split` | `DEB-01`, `DEB-02`, `DEB-03`, `DEB-04`, `DEB-05`, `DEB-07`, `DEB-08`, `DEB-09`, `DEB-10`, `DEB-11` |
| `sequence` | `DEB-06`, `DEB-12`, `DEB-13`, `DEB-14` |
| `retain` | `P0-ACCEPT`, `P0-REBIND`, `FINAL-FREEZE`, `FINAL-REVIEW`, `FINAL-REPLAY`, `FINAL-USE` |

## Практический смысл разделения

Разделение DEB особенно полезно там, где один umbrella собирает независимые исторические долги: это разные outputs и owners, а не одна гигантская реализация. При этом GY-DEF22 имеет один internal owner route DEB-04; R25 убирает противоречащее повторное назначение в DEB-09. GYD-15 сохраняет свой отдельный FA1 mechanism, общий source ID не делает его дубликатом.

У больших LIF задач часть complexity неделима: нельзя отдельно решить publication/currentness и потом забыть reconciliation. Здесь важнее последовательные полные checkpoints, а не больше writers. У UI нельзя выдавать API, browser и MACHINE как независимые смысловые контракты; их единый owner result проверяется совместно.

У DES-10 пять разных свойств допускают разные verification campaigns; это не пять повторов global replay. Target-reader comprehension не является основанием остановить инженерную проверку fidelity, но без настоящих readers нельзя заявить comprehension.

P0-ACCEPT, P0-REBIND и четыре FINAL задачи оставлены как coordination/acceptance parents. Их `retain` не означает поручить все операции одному leaf. Они собирают полноту, source selection и реальные joins, а не конкурируют с canonical implementers.

## Как не увеличить перегрузку самим разбором

Новые каталог и examples — инструменты root/lead. Leaf получает только действующий operative context и необходимое замыкание semantic contracts; full family history доступна, но не обязательна для unrelated slices. Не создавать ещё один вручную синхронизируемый task tracker и не пересылать каждому все 121 карточку. Шаблон может быть коротким, но обязательные source clauses не исчезают.

План меняет **способ выдачи**, сохраняя canonical task/criterion registry. Если в actual source две предложенные части не имеют независимой границы, root объединяет их или выбирает sequence, сохраняя coverage; каталог не заставляет строить искусственные интерфейсы.

[Методика, ограничения и review](../../assurance/r25-card-audit.md).
