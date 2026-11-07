# CAL-04 — проверенный последний итерат, final forward и локальный Hessian reuse

**C110 · LANE-10 · B184, B196, B203 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

Основные ремонты реализованы не только декларативно. Последний произведённый кандидат отдельно оценивается; overshoot/NaN не вытесняют проверенное состояние. При изменении весов или step-varying seed historical finalist пересчитывается на финальной сопоставимой цели. Selected forward переносится в final loss/traces projection. Hessian выбранного старта сохраняется вместе с точным local key и переиспользуется только при совпадении; отсутствие/изменение identity требует расчёта.

**Небольшой остаток C110-R01:** если последний state вовсе не изменился и loss равен прежнему, его уже выполненный final forward отбрасывается и вычисляется снова. **C110-G01:** native parameter-connected JAX/optax integration остаётся UNRUN.

**5 MATCH; 3 неизменённых pure test bodies / 3 cases PASS.** MATCH включает defect witness; это не product PASS. Остальные existing JAX tests только прочитаны.

## 2. Матрица оснований

| ID | Исходный ремонт | Фактическая способность | Остаток |
|---|---|---|---|
| B184 | Shared `_forward_evaluation` возвращает total, base vector, traces и penalties; selected snapshot передаётся final projection. | Улучшенный candidate требует один final forward; total/per-target/trace берутся из него. Нет обязательного тройного scan. | R01: stationary tie повторяет тот же forward. Full typed report/native integration G01. |
| B196 | Last produced state оценивается, затем сравнивается с проверенным finalist. Для final weights/replica есть повторная сопоставимая оценка baseline. | 0→0.5 улучшает f=(x−1)²; 4 и NaN отвергаются. Изменённые weights и step mode проверены exact statements. | G01: actual Adam/JAX budget/gradient paths не исполнены. Два проверенных финалиста не означают глобально лучший state всей истории. |
| B203 | Local Hessian result, identifiability и key сохраняются в run record; final key проверяется до reuse. | Три local Hessians остаются тремя после exact selected reuse. Смена point .25→.5 даёт четвёртый расчёт и иную матрицу; disabled не вызывает kernel. | G01: NumPy fallback с explicit unavailable-derivative seam, не native JAX Hessian. |

## 3. Producer → consumer

Optimizer step возвращает loss предыдущего state и новый state. Код сохраняет `prev_u_state` вместе с измеренным loss, затем отдельно оценивает последний candidate. При несопоставимых весах или step seed baseline пересчитывается на том же `final_step_idx=0` [S01:3165–3233](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py#L3165-L3233). Это полезная deliberate evaluation, не избыточность, которую следует убрать ради счётчика.

Run record переносит selected forward, state, weights и Hessian identity. Final projection вызывает forward только при отсутствующем snapshot [S01:3313–3326](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py#L3313-L3326). Differentiable objective closures продолжают строить traces от переданных параметров — готовый detached trace внутрь Hessian не подставлен.

Local key включает point, coordinate names, weights, seed/strategy, horizon, dtype, damping/rank tolerance/max parameters, fidelity policy и optional ordered objective digest [S01:459–554](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py#L459-L554). Это локальный reuse внутри одной неизменной run closure, не общий cache между разными механизмами/данными.

## 4. Выполненные проверки

| Проверка | Результат |
|---|---|
| P01 | Три pure unchanged bodies: last-iterate selection, key identity, nonfinite point refusal — PASS. |
| P02 | Exact finalization/projection: improved candidate выбран; overshoot/NaN отвергнуты; changed weights и step final replica сопоставлены; разные точки с равным loss сохраняют прежний state. |
| P03 | Candidate point=baseline point=0, weights=1, step=0: два identical final forward calls. Уже рассчитанный snapshot не сохранён. |
| P04 | Exact key match принят; каждое из 14 identity fields отдельно изменено и отвергнуто; None/nonfinite также отвергнуты. |
| P05 | Actual local-Hessian/reuse statements: points −.5,.25,1 дают 3 calls; exact selected reuse сохраняет тот же объект. Point .5 требует call 4, matrix около 3 вместо .75. Disabled добавляет 0 calls. |

[Probe](../04_Проверки/C110_CAL04/probe_cal04.py) · [diagnostics](../04_Проверки/C110_CAL04/bounded_diagnostics.json) · [commands/exit/logs](../04_Проверки/C110_CAL04/commands.json).

Счётчики P02/P03 относятся к финальной фазе, не включают предыдущий training step. P05 использует настоящую finite-difference реализацию с NumPy и parameter-connected quartic fixture; JAX derivative seam объявлен недоступным. Числа вызовов не переведены в проценты ускорения.

## 5. C110-R01 — stationary tie теряет пригодный snapshot

После проверки candidate `candidate_selected` требует строго меньший loss. При равенстве выбирается historical state, а `selected_forward` берётся из `baseline_forward`, который при fixed seed и неизменных weights мог не вычисляться [S01:3188–3233](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py#L3188-L3233). Далее None вызывает новый final forward.

P03 задаёт точное равенство самих states и objective identity, а не только loss: candidate=baseline=0, одинаковые weights и final step. Exact statements вызывают fixture дважды с одинаковыми аргументами. Это допустимая граница stationary/нулевого обновления; текущий optimizer не запускался, частота не измерена.

**Оставшаяся работа:** сохранять уже рассчитанный snapshot, когда точная выбранная point/objective identity совпала, даже если tie policy оставляет прежний state. Нельзя просто reuse-ить по равенству scalar loss: отдельный P02 control с points 0 и 2 имеет равный loss 1, но должен сохранить point 0. Не менять tie policy скрытно и не превращать snapshot в detached derivative cache. Новый глобальный cache не нужен.

## 6. Сохранить и доквалифицировать

Сохранить last-candidate evaluation, проверенный baseline, final weights/replica, histories/diagnostics, shared snapshot, parameter-connected Hessian closures и точный local key. Изменение точки или политики должно по-прежнему запрещать reuse. Не удалять нужные Hessians других стартов, если selection policy ими пользуется.

C110-G01: все existing native witnesses в `test_cal_04.py` прочитаны, включая actual Calibrator с synthetic parameter-connected scan, nonfinite gradient, fixed/step seed, scan counter и Hessian identity mismatch. Они не исполнены: JAX/pytest отсутствуют, native import в Python 3.12.14 блокируется на 3.14-only syntax `uncertainty.py:287`. Существующий test fixture отключает JIT и подменяет scan, поэтому даже его будущий PASS нужно отличать от full production simulation.

Один общий LANE-10 integration может покрыть связанные invariants. Требуется отдельное native derivative подтверждение; синтетическая curvature не inference/эмпирическая authority. Full typed report/CAS persistence здесь не выполнялись. Фаза implementation tasks не начата.

[Исходная карточка](../05_Источники/CAL-04_исходные_строки.txt) · [pinned sources](../05_Источники/C110_источники.json) · [остатки](../01_Реестры/C110_остатки.json) · [точные границы](../04_Проверки/C110_CAL04/Чтение_и_границы.md).

**110/127 — промежуточный аудит. Следующий CAL-06.**
