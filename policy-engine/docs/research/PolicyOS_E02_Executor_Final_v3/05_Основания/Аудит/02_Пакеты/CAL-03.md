# CAL-03 — fresh spans и честный выбор результатов нескольких стартов

**C109 · LANE-10 · B183, B195 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

Основные прежние дефекты исправлены содержательно. `_calibration_span_context` создаётся внутри каждого restart и добавляет start index, не меняя общий attributes mapping. Selector предварительно исключает nonfinite/malformed loss, различает missing Hessian, известный inf/nonfinite/large condition и допустимый condition. Если все конечные результаты диагностически ограничены, работа не уничтожается: возвращается лучший finite loss с явным fallback reason.

**Остаток C109-R01:** actual single-run caller обходит исправленный public selector и передаёт nonfinite run в final phase. **C109-G01:** два полноценных native starts с OTel/JAX ещё не квалифицированы.

**5 MATCH; 16 неизменённых test bodies / 16 cases PASS в bounded runner.** Это не native suite PASS и не доказательство глобального минимума.

## 2. Матрица исходных оснований

| ID | Исходный ремонт | Реальная цепочка | Остаток |
|---|---|---|---|
| B183 | Fresh context factory вместо одного повторно используемого span_cm; отдельные no-op contexts. | Actual loop вызывает factory на каждом start; existing tests и P02 проходят три настоящих stdlib one-shot contexts. Shared attributes не мутируют. | G01: OTel SDK/exporter и два full optimizer starts UNRUN; no-op успех не выдаётся за telemetry qualification. |
| B195 | Finite loss admission; missing отдельно от inf/NaN/large; явный fallback; alternate policy также фильтрует loss. | Whole selection module исполняется. 24 дополнительных table cases; constant/quadratic actual fallback Hessian передают raw-condition inf/1 реальному consumer. | R01: один actual run выбирается прямым else, без finite guard. Native JAX Hessian G01. |

## 3. Owner и producer → consumer

Lifecycle wrapper окружает весь calibration call, а per-start factory живёт внутри restart loop [S02:3083–3087](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py#L3083-L3087). `_calibration_span_context` возвращает свежий `nullcontext` либо новый tracer context с `calibration.start_index` [S02:875–896](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py#L875-L896). Наблюдаемость не выключена и число стартов не сведено к одному.

Каждый run сохраняет state, final weights, histories, diagnostics, Hessian и selected forward. При нескольких runs они преобразуются в actual SingleRunResult, затем index/reason выбирают тот же runtime record [S02:3248–3304](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py#L3248-L3304). Сохранение histories/ограниченного результата полезно. Full optimizer и final report не исполнялись.

Hessian сохраняет raw eigenvalues для condition, отдельно от repaired matrix. P04 подтверждает на настоящем NumPy finite-difference fallback: constant objective имеет raw eigenvalue 0, repaired 1e-6, **condition inf**, а quadratic — raw 2 и condition 1. Selector выбирает второй, даже если у первого меньше loss. Derivative seam намеренно недоступен; это не native JAX test.

## 4. Что выполнено

| Проверка | Наблюдение |
|---|---|
| P01 | 11 CAL-03 + 5 test_multi_start unchanged bodies: 16 PASS. Shape/config dependencies — selected actual DTOs. |
| P02 | Три fresh stdlib one-shot contexts входят/выходят; попытка повторного входа в первый отвергается. Attributes не изменены. |
| P03 | 14 condition/order и 10 invalid-loss/selection controls. Missing сохраняет loss-only режим; inf/NaN/negative/large/malformed condition не обходят best_loss filter. |
| P04 | Actual fallback Hessian → actual selection: known degeneracy не названа missing. Выбран finite acceptable кандидат. |
| P05 | Exact caller statement: single inf проходит в selected_run; public selector отвергает его; при двух runs actual caller выбирает finite 0.5. Diagnostic сохранён. |

[Логи и команды](../04_Проверки/C109_CAL03/commands.json) · [probe](../04_Проверки/C109_CAL03/probe_cal03.py) · [результаты](../04_Проверки/C109_CAL03/bounded_diagnostics.json).

## 5. C109-R01 — исправленный helper не охватывает single-run caller

`select_best` проверяет наличие finite loss **до** ветки одного run [S01:35–53](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/multi_start.py#L35-L53). Но actual caller вызывает его только при `len(multi_start_runs) > 1`; иначе берёт `[0]` напрямую [S02:3267–3304](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py#L3267-L3304).

P05 сначала исполняет actual `_select_lower_loss_state`: previous inf и candidate NaN не дают конечного результата. Затем точный selection if/else получает fixture runtime dictionary. При одном run nonfinite state выбран, при двух с finite 0.5 выбирается пригодный. В обоих случаях используется unchanged caller statement. Проверка самого public selector на единственном inf получает ValueError.

**Ограничение вывода:** доказан обход finite-result admission при переходе к final phase. Diagnostics о nonfinite gradients не теряются. Полный optimizer, constructor/return report, CAS persistence и downstream scientific acceptance не запускались; source report field `total_loss: float` не выдаётся за выполненный end-to-end приём такого отчёта.

**Оставшаяся работа:** согласовать single/multi finite-result admission до final projection. Отсутствие конечного кандидата должно иметь явный отказ либо отдельный диагностический result contract. Конечный, но ill-conditioned результат можно сохранить с точным ограничением. Не уничтожать полезные histories, не запрещать все ограниченные модели и не исправлять уже правильную raw-Hessian диагностику вместо consumer.

## 6. Сохранить и доквалифицировать

Сохранить fresh factory, start identity, no-op режим, finite loss filter, explicit condition statuses, deterministic ties, missing-Hessian loss-only режим, честный fallback и обе selection policies. Best-identifiability — заявленная иная ranking policy, не автоматическое обещание прохождения best-loss threshold. Табличное имя test_global_minimum не доказывает глобальную оптимальность системы.

C109-G01 требует supported-runtime интеграции: два actual starts с OTel и без него, lifecycle/status и primary exception policy, маленький настоящий JAX Hessian, final reason/record consistency. Существующий lifecycle test с real metrics provider прочитан, но не запускался. JAX/OTel/pytest отсутствуют; native calibration import в Python 3.12.14 блокируется на 3.14-only syntax `uncertainty.py:287`. Это environment limitation, не новый product defect. Общий integration для LANE-10 может покрыть несколько пакетов без искусственного дублирования.

Synthetic curvature/selection не эмпирическая authority и не научная идентификация. Фаза implementation tasks не начата.

[Исходная карточка](../05_Источники/CAL-03_исходные_строки.txt) · [pinned sources](../05_Источники/C109_источники.json) · [остатки](../01_Реестры/C109_остатки.json) · [границы](../04_Проверки/C109_CAL03/Чтение_и_границы.md).

**109/127 — промежуточный аудит. Следующий CAL-04.**
