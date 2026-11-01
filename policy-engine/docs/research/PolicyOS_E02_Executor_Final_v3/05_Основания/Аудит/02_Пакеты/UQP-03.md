# UQP-03 — остановка MC, conditional result и непокрытая область

**C115 · LANE-10 · B193, B194 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

Batch-boundary дефект исправлен: очередной batch разрезается до следующего checkpoint. Partial failures больше не выдаются за безусловный закон: сохраняются полезные successful samples, типизированные per-draw failures, requested/attempted/successful/unattempted counts, conditional semantics и gate=false. Typed transient повторяет тот же invocation один раз; global ошибки не поглощаются как шумные draws.

**5 MATCH; 16 неизменённых test bodies PASS.** Впервые в этой цепочке исполнен actual selected legacy MC **вплоть до полного result builder и IR DTO**, но с NumPy вместо JAX PRNG; это не native package/CAS/normative run. **Нового подтверждённого product defect не объявлено.** Width stopping остаётся намеренной эвристикой, не точностью выбранного функционала; G01/G02 открыты.

## 2. Матрица исходных оснований

| ID | Исходный ремонт | Actual capability | Остаток |
|---|---|---|---|
| B193 | Проверка на достигнутой границе; определить предмет остановки. | Batch50/60 в random/Sobol доходят100 draws, не240. Existing test отдельно подтверждает boundary60 при batch50. Early result non-gating,140 unattempted при budget240. | G01: criterion остаётся relative **full output width**, несмотря на имя half_width; это не MCSE/quantile/CDF error и не sequential certificate. |
| B194 | Failed mass/draw identity/conditionality, same-draw retry, global error escape. | Exact100 symmetric draws:50 failures,50 samples со mean50/99; failure indices0..49 сохранены, denominator complete, output coverage incomplete, gate=false. Typed transient retry не увеличивает logical draw count. | G02: full native persisted/served-source authority route не квалифицирован; mechanism of missingness не восстановлен. |

## 3. Producer → consumer

`_adaptive_batch_size` ограничивает batch ближайшей checkpoint boundary [S01:1957–1976](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py#L1957-L1976). `_check_adaptive_stop` после минимального числа valid сравнивает `(hi−lo)/|point|` с target [S01:1978–2004](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py#L1978-L2004). Existing test намеренно сохраняет broad99/101 distribution broad, а не требует исчезновения физической uncertainty от большогоn.

Recorder связывает missing/nonfinite/solver failures с draw index и sampled-input SHA. Result builder отделяет logical draws от physical attempts, сохраняет failure ledger и выставляет conditional/non-gating output при неполноте [S01:2148–2207](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py#L2148-L2207), [S01:2344–2363](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py#L2344-L2363). Наличие50 useful values не скрывает отсутствующую половину входной области.

Actual classifier обходит bounded exception graph: известный global cause имеет приоритет; transient допускается лишь для root при complete/acyclic graph [S03](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/evaluation_failures.py#L96-L140). Retry ограничен двумя physical attempts одной неизменённой invocation, а не новой независимой репликой.

Generic persisted reader консервативно не возвращает admitted numeric envelope только по внутренне согласованным producer counts: требуются дополнительные successful-draw/verifier и source-owner основания [S07:2321–2483](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/uncertainty.py#L2321-L2483). Это source-read, не исполнение Science bridge. Existing fresh normative test показывает ожидаемый limited consumer contract, но здесь не запускался.

## 4. Выполненные проверки

| Проверка | Результат |
|---|---|
| P01 |16 existing bodies PASS: boundary/width, partial/nonfinite/missing/multiple outputs, all-failed/complete controls, adaptive cap, exact symmetric draws, transient/global cases. |
| P02 | Random/Sobol × batch50/60:100 draws,101 physical calls,140 unattempted; heuristic_range, gate=false. |
| P03 |99/101 приn200 и10000: full relative width.02, half-width.01; target.015 не срабатывает. Constant output срабатывает. Это width heuristic, не MC precision. |
| P04 |100 fixed symmetric draws→50 failures/50 retained values, mean≈.50505; failure indices0..49, denominator complete=true, output coverage=false. Actual result DTO JSON reload сохраняет carrier и запреты. |
| P05 |Transient повторяет x=−.25 ровно дважды; root transient с PermissionError cause классифицируется global и вызывается один раз; cycle остаётся unknown. |

[Probe](../04_Проверки/C115_UQP03/probe_uqp03.py) · [полный partial result](../04_Проверки/C115_UQP03/run01/partial_result.json) · [diagnostics](../04_Проверки/C115_UQP03/bounded_diagnostics.json) · [команды/логи/exit codes](../04_Проверки/C115_UQP03/commands.json).

## 5. Сохранить и доквалифицировать

**C115-G01 — предмет остановки.** Batch repair не означает научную аттестацию stopping. Текущий test и historical plan намеренно задают output-width criterion; нельзя объявлять его багом только потому, что он не оценивает MC error среднего. Но имя `ci_half_width_target`, actual full width и сообщение «converged» требуют однозначного semantic contract. Нужен явный выбор width-based decision heuristic либо отдельного functional-specific precision режима с допустимым sequential plan. Не заменять interval индивидуального результата `σ/√n` и не повышать candidate-only результат до confidence claim.

**C115-G02 — native/source authority.** Сохранить50 полезных результатов, distinct failed/unattempted mass, exact per-draw identity, typed retry/global precedence и read-side refusal. Не заполнять NaN нулями и не отменять весь partial result без причины. Для безусловного вывода нужны дополнительные основания о missingness или восстановленная область, не просто достаточное абсолютное число valid.

Выполнены actual selected legacy producer/result DTO, NumPy PRNG binding и real SciPy Sobol. Native JAX package graph, CAS persistence, fresh Science/normative consumer, served deployment/source binding и institutional admission остаются UNRUN. Python3.12.14 блокирует import на3.14 syntax uncertainty.py:287; pytest/JAX отсутствуют. Lightweight Core errors/classifier импортированы реально. Complete local control с gate=true не является доказательством внешнего допуска.

[Исходная карточка](../05_Источники/UQP-03_исходные_строки.txt) · [pinned sources](../05_Источники/C115_источники.json) · [остатки](../01_Реестры/C115_остатки.json) · [границы](../04_Проверки/C115_UQP03/Чтение_и_границы.md).

**115/127 — LANE-10 рассмотрен ограниченно. Следующий DOE-01. Осталось12 пакетов; фаза заданий исполнителю не начата.**
