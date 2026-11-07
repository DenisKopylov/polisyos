# DDM-02 — актуальное основание, observed source и R2 override

**C122 · LANE-11 · LA-054, LA-055 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

Historical FP pass больше не достаточен для текущего gate. Actual checker связывает report digest, audit, subject, effective time и отдельно выбранный observation source; persisted projection теряет private authority и требует свежего rebind. Наблюдённая пустота различается с отсутствием source; изменения source bytes, expiry, invalidation и подменённый basis отклоняются.

**5 MATCH; 33 unchanged test bodies / 52 cases PASS. C122-R01 (low):** прямой registry builder может пометить applicability bound для earlier foreign-model shift, если last event принадлежит target. Actual monitor такой вход отвергает; public final gate всё равно отказывает finite-only authority. Нормативный bypass не доказан.

## 2. Матрица исходных оснований

| ID | Исходный ремонт | Actual capability | Остаток |
|---|---|---|---|
| LA-054 | Связать report/expiry/triggers и subjects/budget/window, не считать historical pass текущим разрешением. | Actual checker, private evidence, strict source selection, complete consumed-basis comparison, JSON rebind и preserved reasons работают. Before/at/after expiry различимы; late finite fact разрешён по явному профилю. | R01: all-event model identity не проверяется в direct-builder route. G01: production observation owner отсутствует; G02: actual FP report provenance/native scientific qualification. |
| LA-055 | Разделить baseline eligibility, veto и ограниченный R2 signoff; empty-alert не unavailable feed. | R4/R3 false — binding veto; только R2+signoff проходит conditional helper; R1/R0 и failed certificate не проходят. Public finite source не становится production grant. | Conditional table не доказывает final positive admission. Signoff bool не authority; versioned policy context G02. |

## 3. Producer → consumer

[Existing validity owner](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/calibration/audit.py#L161-L269) сравнивает полный projected audit с тем же report, пересчитывает digest и получает triggers из actual selected source, а не доверяет списку caller. [Finite source](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/calibration/observations.py#L119-L205) читает bounded regular file, сверяет subject/report/checkpoint и повторно проверяет current bytes. Scope прямо `finite_replay_only`.

[Monitor](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/integration/monitor.py#L89-L154) связывает projection до builder. [Rebind](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/integration/model_registry.py#L232-L316) заново читает source inputs, recomputes readiness и не восстанавливает private authority из public markers.

[Public gate и conditional table](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/integration/model_registry.py#L318-L416) разделены. Независимые certificate/identity/validity/applicability guards предшествуют state/override table. Finite replay не проходит финальную production boundary, даже если текущий typed calibration status valid. Это полезный честный предел, не повод удалить gate.

## 4. Проверки

| Проверка | Результат |
|---|---|
| P01 |33 unchanged bodies/52cases PASS: expiry boundary, matching trigger, source change, unavailable/empty, missing basis, false budget consumption, full readiness projection tamper, same-model detector/calibration/regime mismatch, foreign subjects, historical/reloaded refs и exact rebind. |
| P02 |10 conditional state/signoff cases; R4/R3 veto сохранён; public failed certificate блокирует все5 states даже с signoff. Positive conditional result не приравнен к public grant. |
| P03 | Earlier shift model=another-model + good last target: direct builder applicability bound без reasons. Monitor ValueError; final gate false с finite-replay reason. |
| P04 | Факт на10 дней старше snapshot принимается finite profile как late fact; candidate bound, production permission=false. Future/checkpoint mismatch controls входят в P01. |
| P05 | YAML default actions и lambda_shift совпадают с code. Policy_id есть в YAML, но decision не проецирует version. Free-text conditions не исполнялись. |

[Probe](../04_Проверки/C122_DDM02/probe_ddm02.py) · [все52 cases](../04_Проверки/C122_DDM02/run01/existing_cases.json) · [наблюдения](../04_Проверки/C122_DDM02/run01/observations.json) · [команды](../04_Проверки/C122_DDM02/commands.json).

## 5. Остаток и сохраняемое поведение

**C122-R01 — earlier-subject candidate binding (low).** [Identity helper](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/integration/model_registry.py#L437-L476) сверяет last shift, а [all-shift loop](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/integration/model_registry.py#L718-L730) — detector/calibration/regime, но не model subject каждого earlier event. Совпадение top-level source context не доказывает nested subject. Расширить existing reconciliation на каждый consumed event; не строить новый registry. [Сохранённый candidate](../04_Проверки/C122_DDM02/run01/foreign_earlier_candidate.json) остаётся non-authoritative. Private checker evidence получено от настоящего owner; token не подделывался. Защита monitor и finite-only final refusal сохранены.

**C122-G01 — production applicability.** Единственный admitted source здесь finite replay; отсутствует легитимный production observation owner, доказывающий selection/coverage/currentness. Не превращать synthetic enumerated snapshot в институциональное основание. Положительная R2 policy-table проверка не снимает этот gap и не подтверждает полномочия человека по bool signoff.

**C122-G02 — policy/scientific/native qualification.** Default YAML/code parity подтверждена, но policy version не проходит через RegistryGateDecision; неизвестная версия не имеет отдельного установленного intake. Это qualification gap, не воспроизведённое смешение реально поддержанных policies. Actual calibrate_detector/stationary streams, statistical FP/FDR guarantees, full native pytest и supported3.14 profile UNRUN. Report/holdout/delay numbers — fixtures, не empirical authority.

Сохранить historical pass как исторический факт, report identity/digest, current effective time, explicit unavailable, expiry reasons, exact source basis, non-overridable guards и R2 exception. Не чинить простым AND, отменяющим R2; не подменять valid_until строкой horizon30d и не создавать universal DSL. Реальные deployment/retrain/ticket actions не запускались.

[Карточка](../05_Источники/DDM-02_исходные_строки.txt) · [pinned sources](../05_Источники/C122_источники.json) · [остатки](../01_Реестры/C122_остатки.json) · [границы](../04_Проверки/C122_DDM02/Чтение_и_границы.md).

**122/127. Следующий LEX-01; осталось5 пакетов. Фаза заданий исполнителю ещё не начата.**
