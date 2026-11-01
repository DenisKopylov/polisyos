# CAL-02 — оси, веса, нулевая опора и общий calibration objective

**C108 · LANE-10 · B179, B180, B181, B182 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

Основной ремонт не фиктивен: exact shape checks запрещают vector/column broadcasting; sample quality нормализуется внутри таргета, priority применяется после reduction; нулевой total weight получает безопасный внутренний знаменатель; масштаб выбирается по реально наблюдаемой training опоре до оптимизации. Shared forward, GradNorm components, обе Hessian closures и final loss projection используют один base-vector путь.

**Полного закрытия нет.** C108-R01: mean/std по большим конечным float32 наблюдениям переполняются и тихо заменяются epsilon. C108-R02: split labels реально произведены, но training mask ограничивает только scale, а не measurement objective. C108-G01: настоящий reverse-mode gradient/JIT и full optimizer остаются UNRUN.

**5 MATCH; 13 неизменённых test bodies / 13 cases PASS в явно ограниченной NumPy-фикстуре.** MATCH включает воспроизведение дефектов, не product PASS. Native suite не запускалась.

## 2. Матрица исходных оснований

| ID | Исходный ремонт | Фактическая способность | Остаток |
|---|---|---|---|
| B179 | `pointwise_base_loss` и weighted reducer сравнивают точные shapes; quality и scale masks проверяются отдельно. Blanket flatten отсутствует. | Existing vector/column и mask-shape bodies отвергают неоднозначность, обычные MSE/Huber работают. | G01: JIT route не исполнен. Проверки не доказывают семантику произвольных одинаковых axes без upstream contract. |
| B180 | Quality умножается на residual внутри нормированного среднего; target priority вынесен наружу. | 9:1 против 1:9 даёт 90 против 730; P05 показывает 96 против 736 с одинаковыми penalties 6 во всех выбранных objective consumers. | R02: внутри measurement objective не применяется уже существующий split. Полные derivatives G01. |
| B181 | `safe_total_weight` определён до `where`, отдельный support status и общий no-support block сохраняются. | P02: finite masked loss 0, support false; nonfinite prediction остаётся +inf. | Настоящий gradient/JIT test прочитан, но UNRUN. Primal zero не признан успешной подгонкой. |
| B182 | Coverage/finite и train masks применяются при фиксированном scale; placeholders другого ряда не меняют проверенный масштаб 10. | Existing mask test проходит, изменение validation не меняет training scale. | R01: переполнение редукции. R02: training scale не означает training-only fit. |

## 3. Producer → consumer

Actual ObservationRecord → compiler строит shared axis, zero placeholders, coverage/trust и split labels; splitter действительно различает train/validation/test/holdout [S05:48–133](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/observation/compiler.py#L48-L133). Calibrator сначала выбирает observed/training scale [S03:2526–2568](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py#L2526-L2568), затем adapter отдаёт sample quality без priority. Base vector применяет reducer, общий forward суммирует base × priority и penalties.

P05 исполняет неизменённые выбранные consumers, но simulation и transforms подставлены фиксированными fixtures. Обе Hessian objective closures совпадают с primal loss; **Hessian и jacrev не вычислялись**. Final report берёт total из shared forward, а per-target — base × final weight [S03:3313–3327](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py#L3313-L3327). Это source-подтверждение, не выполненный full report. Отдельные descriptive fit metrics не должны ошибочно называться тем же нормированным objective.

## 4. Доказательства

| Проверка | Фактическое наблюдение |
|---|---|
| P01 | 5 CAL-02 и 8 test_loss bodies: 13 PASS, без изменения bodies. Gradient/JIT body не исполнялся. |
| P02 | Полностью masked finite primal равен 0 и support false; nonfinite residual остаётся +inf. |
| P03 | Mean_abs([3e38,3e38]) и std([1e20,2e20]) в actual helper дают epsilon 1e-8. Float64 reference остаётся конечным; с reference scale выбранный loss конечен. |
| P04 | Actual compiler labels train/validation. Изменение только validation 10→30 меняет objective 0→2, scale остаётся 10. All-validation control имеет no training support, но ненулевой objective около 5e17. |
| P05 | Actual выбранные forward/loss/обе Hessian primal closures дают 96 или 736; GradNorm weighted components согласованы. Только primal wiring при fixed-forward fixtures. |

[Диагностика](../04_Проверки/C108_CAL02/bounded_diagnostics.json) · [команды и exit codes](../04_Проверки/C108_CAL02/commands.json) · [основной probe](../04_Проверки/C108_CAL02/probe_cal02.py) · [shared objective probe](../04_Проверки/C108_CAL02/probe_shared_objective.py).

## 5. C108-R01 — переполнение scale не равно отсутствию данных

`np.asarray` сохраняет float32, `np.mean`/`np.std` не повышают precision, а любой nonfinite scale возвращает default epsilon [S03:724–763](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py#L724-L763). В P03 все observed/training masks положительны, исходные values конечны. Для mean_abs reference около 3e38, для std около 5e19; actual scale в обоих случаях 1e-8. При прогнозе 0.99 × observed actual выбранный loss становится +inf, а reference-scale loss — около 0.0001 / 0.001.

Это ограниченный numerical defect на representable входах, не основание снимать finite guard. Сохранить masks и frozen scale; стабилизировать существующую редукцию, отличать overflow от no-support. Большие synthetic значения не доказывают распространённость проблемы в реальных данных. Scale helper исполнен фактически; loss — с NumPy binding, native JAX не квалифицирован.

## 6. C108-R02 — producer partition не ограничивает fit consumer

Compiler сохраняет partition labels, scale читает `train`, но `_base_vec_from_traces` передаёт все наблюдения в pointwise loss и sample-quality reducer без split mask [S03:2780–2839](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py#L2780-L2839). Preflight `measurement_support` также проверяет только quality; отсутствие training scale support записывает diagnostic, но само по себе не исключает fit.

P04 использует реальный compiler/splitter, а не вручную выдуманный раздел. Первая точка train=10, вторая validation=10, прогноз [10,10]. Изменение только validation до 30 меняет objective 0→2 при неизменном масштабе 10. Train-only control остаётся 0. All-validation control показывает отдельность support и scale support, а не доказанный успешный запуск optimizer.

**Оставшаяся работа:** протянуть существующий split contract до общей разрешённой fit support и отдельно считать оценочные разделы. Если намеренно разрешён full-data fit, роль данных должна быть явной, без ложного обещания независимой validation. Не нужен второй splitter или новый framework. Не менять silently coverage ради сокрытия раздела. Full Calibrator/production panel не запускались: утверждение ограничено actual producer и выбранным consumer, не статистической величиной утечки в эксплуатации.

## 7. Сохранить и доквалифицировать

Сохранить exact shape refusal, quality/priority separation, finite guards, безопасный знаменатель, явные no-support diagnostics, frozen scale, shared forward и существующие objective consumers. Не вводить `nan_to_num`, положительные fake weights или универсальное flatten. Synthetic fit не эмпирическая authority.

C108-G01: требуется поддерживаемая Python/JAX/optax среда и existing reverse-gradient/JIT test, плюс общий lane integration для compiler → calibration → GradNorm/Hessian/report. Native imports здесь BLOCKED на 3.14-only syntax `uncertainty.py:287`, JAX и pytest отсутствуют. Это environment limitation, не product defect. Ничего не устанавливалось.

Первый shared harness остановился до вычислений: наш внешний selector ожидал одну Hessian closure, а их две. Неуспех сохранён; второй запуск проверяет обе. Старые результаты не перекрашены.

[Исходная карточка](../05_Источники/CAL-02_исходные_строки.txt) · [pinned sources](../05_Источники/C108_источники.json) · [остатки](../01_Реестры/C108_остатки.json) · [точные границы](../04_Проверки/C108_CAL02/Чтение_и_границы.md).

**108/127 — промежуточный аудит. Следующий CAL-03. Фаза заданий исполнителю не начата.**
