# E02: решения G по HTE, CAN, текущей неопределённости и Fabric exceptions

Дата: 21 октября 2026. **Финальный архитектурный выбор для реализации.** `architecture_selection=selected_by_G`; `code_acceptance=false`; `closure_ids=[]`. Этот пакет не является новой ратификацией system-design-decisions и не меняет принятые [AD01–03](../architecture-decisions-2026-10-20/06-final-decisions-and-solo-review.md).

| Решение | Что реализовать | Что этим не устанавливается |
|---|---|---|
| [AD04 — HTE](04-hte-point-and-inference.md) | Один versioned outcome: рассчитанная точка, точка с обоснованным в своей границе интервалом, либо отказ. Native интервал привязан к точным evaluation rows и попытке; неподтверждённый fallback исключён из нового пути | Population-ATE coverage, causal identification, post-selection validity, calibration и publication authority |
| [AD05 — CAN / LA-021-1](05-canonical-profile-and-context.md) | Общая канонизация и хэширование при строгой семантике конкретного Core/IR reader; никаких переписываний CAS и автоматического расширения IR tags | Producer attestation, наличие raw profile по одному digest, currentness или универсальная взаимозаменяемость facades |
| [AD06 — B161](06-current-scoped-uncertainty.md) | Отдельная текущая проекция; конкретное первое уточнение `unassessed→assessed` на одном frozen basis. История и другие ограничения сохраняются | Универсальное снижение уже измеренного риска, независимость источников или превращение routing score в вероятность |
| [AD-E02-FABRIC-N818-01](09-fabric-exception-identities.md) | Сохранить семь exception definitions; точечные N818 annotations с обоснованием и удаление только N818 из общего Fabric-ignore с generated companions | Новая public-stable классификация deep imports, human code approval, lint/runtime PASS или finding closure |

Для вопроса `880c238d` исполнитель использует отдельный [N818 implementation scope и acceptance](09-fabric-exception-identities.md) и [source-qualified receipt](fabric-exception-identities-inputs.json). Это дополнительное узкое решение; оно не пересматривает AD01–06. Старый seven-line patch требует config companion: без него общий ignore скрывает новые нарушения и может конфликтовать с RUF100.

В AD04 **интервал backend для среднего по выбранным строкам** и **обоснованный population interval** — разные утверждения. Первый можно честно хранить и показывать с условиями, даже когда второе недоступно. В AD06 отсутствие оценки — отдельное состояние, а не численный риск 1.0. Это позволяет реализовать полезную работу, не объявляя недостающие основания существующими.

Исполнитель начинает с [порядка реализации и границ самостоятельных решений](07-implementation-handoff.md). [Исследование, атаки и исправления](08-research-and-critical-review.md) объясняют выбор и отклонённые варианты. [inputs.json](inputs.json) содержит точные входные SHA-256 и source frames.

## Уровень доказанности

Прочитаны пять названных входных документов из candidate checkout; все совпадали с Git blob наблюдаемого `2536eb6dbc946ce5000d2b2da246d7e071b037fc`. Это адрес документов, не global freeze кода. Исследование кода использует указанные в inputs более ранние точные snapshots; рабочий checkout исполнителя продолжает изменяться, и G его не редактировал.

Свежий HTE runtime receipt отделён от раннего неуспешного adapter witness: наличие нового bounded PASS учтено, но не выдано за доказательство inference law или всех consumers. Аналогично CAN scoped replay не переносится на текущий общий HEAD. В этой работе не выполнялись product tests, imports, installs, numerical fits, builds, data scans или production reads. Все новые acceptance signals — обязательства будущей реализации.

Вопрос о PAG при неизвестном юридическом допуске **не решён этим пакетом**: пользователь сообщил, что его факты и миграция consumers ещё проверяются. Не вводить скрытое разрешение/запрет через эти три решения. Общая уже принятая граница candidate/authority сохраняется, но конкретный PAG путь требует своего подтверждённого пакета.

## Что доступно без новых внешних разрешений

Можно реализовать typed contracts, actual producer wiring, first-assessment relation, native conditional inference profile, строгие readers, pinned projections, миграцию consumers и отрицательные проверки. Это внутренние механизмы и исследование опубликованной методологии. Отсутствие внешнего issuer или production workload не является причиной остановить их.

Нельзя самостоятельно создать реальные permissions, custody/currentness факты, доказательство репрезентативности популяции, эмпирическую calibration или специальный закон обновления уже assessed evidence. Их отсутствие ограничивает соответствующий claim, а не весь candidate workflow. Предлагать новый вопрос G следует только после проверки существующих owners и документирования точного противоречия, а не по факту встретившейся неполной цепочки.

Pattern pass: P01/P02/P03/P04/P05/P07/P08/P10/P14/P27/P28/P29/P31/P32/P35/P37/P38/P40/P41. Новые документы выбирают контракт; реальные capability labels и finding dispositions меняются только после source review и deciding runtime evidence. `main` не изменяется.
