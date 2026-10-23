# R16: dispatch композиций и пересчёта

Реализация начинается только после фактической приёмки E02 и scoped accepted-source rebind. [C1–C8](../solutions/16-composed-execution-and-revisions.md) — части существующих задач, не восемь дополнительных root tasks и не линейные восемь волн. Реестр сохраняет 121 задачу. `r16_extension` обязателен вместе с прежними критериями; [machine obligations](../assurance/r16-capability-obligations.json) связывают все дополнения с owner tasks.

## Работа, которую можно вести одновременно

| Lane | После какого соглашения можно готовить | Где требуется реальный supplier для завершения |
|---|---|---|
| GYD-30: compile/order/joint block | Exact port/result/profile meanings и полный actual writer rebind | Реальные participants и свежий joint consumer; выбранные SCC properties подтверждены, не mocked |
| DES-11: clock/state/temporal adapter | Native joint/state/clock interface; schema writer назначен | Реальный temporal execution, full participant restoration/cutoff; warm start не proof |
| LIF-07 + отдельные readers DES-03/GYD-30 | Influence/read-set/use relation, completeness и conservative fallback | Actual dynamic/negative reads и independent selective-vs-clean result |
| CAP-04 + LIF-02 | Source event/cut и currentness contracts | Real enrollment replay и immediate affected-use reaction; нужен actual source event |
| DES-04 + LIF-04 | Revision intent, duty, attempt, desired head/effect contract | Actual admitted event→durable continuation→native trial; dirty event недостаточен |
| CNT-06/08 + GYD-09/10/12 + DES-12 | Selected causal/inference/scenario meaning, existing authorization | Реальный evidence update/return и отдельно qualified world activation; candidate analysis разрешён с declared unknown |
| LIF-06 / OPS-08 / selected CAP-06/OPS-09 | Nested resource/effect accounting contract | Actual aggregate work, terminated processes, bounded external effects; remote lane только если выбран |
| DES-10 / DES-06 / UI-06/08 | Persisted owner-output contract и independent oracle definition | Fresh producer bytes и полная заявленная поверхность; UI не mint-ит authority |

Разделение означает независимые adapters, oracle design, research и disjoint source edits, а не восемь одновременных writers общего файла. Один writer `GYD-30` составляет shared compiler/executor/schema; `DES-03` — search.py; `DES-04` — generation-cycle bridge; `LIF-07` — influence/lineage meaning; `LIF-02` — native epoch/current head. Изменение meaning согласуется до параллельной реализации readers. Точный write set и mandatory companions вычисляются по accepted E02, перечисленные anchors не разрешение менять модуль целиком.

Существующий edge `CAP-04 ← LIF-02` уточняется до `interface_agreement` для независимой подготовки source adapter; actual enrolled replay/currentness consumer требуется для соответствующего composed claim. Остальные CAP-04 prerequisites сохраняются. Новый preparation edge `DES-03 ← LIF-07` имеет `interface_agreement`, а не owner-completion. Actual influence supplier нужен для **selected reuse/composition acceptance**, иначе интерфейсный mock был бы ложным proof. C4/C5/C7 suppliers в composed proof обязательны по заявленному свойству; не добавлять all-to-all start edges. Если native owner после E02 уже выполняет свойство, выполнить wire/verify и сохранить его; нельзя создавать второй engine ради task label.

## Один shared cycle, разные локальные checkpoints

1. На accepted source согласовать минимальные typed meanings, currentness boundary и независимые semantic oracles. Исследования contract semantics можно делать до E02, product writes — после.
2. Выполнить native stateless composition и bounded exact reuse; параллельно clock/state и scientific-update adapters. Неподдержанный optional protocol не задерживает независимый supported profile.
3. Соединить actual event→duty→trial→artifact→fresh reader; проверить исправления, отмену, competing revisions и обязательную immediate public reaction. Эти связи могут соединяться в порядке поступления готовых suppliers.
4. До freeze owners дают scoped checks и независимые reviews. Изменения shared contract получают delta consumer checks. Все selected R16 obligations присоединяются к existing FINAL-FREEZE/FINAL-REVIEW/FINAL-REPLAY, не новой общей wave.

## Compute и review ресурсы

Материализация общего graph/state store, current-head writer или shared schema сериализуется только на время фактической мутации. Независимые actors/branches и stateless nodes могут исполняться параллельно, когда numerical profile это допускает. Jacobi, Gauss–Seidel, asynchronous updates и common-random-number coupling не подменяют друг друга ради скорости.

На nested execution один aggregate resource owner; waiting parent не удерживает единственный permit, нужный child. Acquired resource сохраняется до подтверждённого release/termination; истечение lease не означает свободную RAM/provider slot. Review immutable source не удерживает writer lease, но изменённый source требует delta review. Никакой цифры гарантированного speedup из количества agents.

Pattern pass: P01/P02/P13/P27/P29/P35/P37/P39/P40/P41. Acceptance: независимая lane стартует после достаточного interface agreement; composed claim не проходит без реальных supplier bytes/property; competing writers общего owner не исполняются одновременно. Runtime UNRUN.
