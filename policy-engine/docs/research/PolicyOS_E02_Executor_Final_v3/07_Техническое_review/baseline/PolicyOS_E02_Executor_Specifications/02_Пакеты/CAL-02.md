# CAL-02 — Одна training-цель без overflow масштаба и утечки split

**LANE-10 · B179, B180, B181, B182 · SHA `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

**Статус:** исполнительская спецификация на последующую работу; требования и будущие тесты здесь не исполнены.

## 1. Практическая цель и тип работы

Калибровать параметры по действительно разрешённой обучающей опоре; сохранённый отчёт и derivatives относятся к той же цели, а независимый validation остаётся независимым.

**Тип:** два ограниченных ремонта C108-R01/R02 + native autodiff квалификация; исходные B179–B182 преимущественно preserve.

Основания: [полный отчёт](../05_Основания/Аудит/02_Пакеты/CAL-02.md), [исходные карточки](../05_Основания/Аудит/05_Источники/CAL-02_исходные_строки.txt), [трассировка](../04_Трассировка/CAL-02.json).

## 2. Уже работает — сохранить

- Exact shape checks до арифметики; никакого blanket flatten/squeeze или nan_to_num.
- Sample-quality нормируется внутри target; priority снаружи. Потери 1/81 при весах 9:1 и 1:9 дают 90/730.
- Safe denominator при нулевой опоре; nonfinite model prediction остаётся недопустимым, а loss0 без опоры не становится хорошим fit.
- Shared time axis/zero placeholders, coverage/trust/split labels, frozen scale и shared forward/GradNorm/Hessian/report.
- CAL-01 остаётся владельцем measurement alignment; generic predictive calibration и DDM FP не объединять с Foundry parameter fit (смысл LK01, хотя прямой LK этому packet не назначен).

## 3. Полная disposition исходных обязанностей и остатков

| ID | Действие | Требования | Почему |
|---|---|---|
| B179 | preserve | REQ-CAL-02-05 | Exact-shape repair уже есть; доказать его сохранение на реальных arrays и upstream mask. |
| B180 | preserve | REQ-CAL-02-04 | Priority repair не повторять; протянуть новую fit measure через существующий общий objective. |
| B181 | qualify | REQ-CAL-02-03, REQ-CAL-02-06 | Safe arithmetic уже есть source/primal; обязательны реальные grad/JIT и no-support outcome. |
| B182 | fix | REQ-CAL-02-01, REQ-CAL-02-02, REQ-CAL-02-05, REQ-CAL-02-07 | Observed-mask repair сохранить; исправить scale reduction и split consumer, не менять compiler roles. |
| C108-R01 | fix | REQ-CAL-02-01 | Воспроизведён overflow finite float32 scale. |
| C108-R02 | fix | REQ-CAL-02-02, REQ-CAL-02-03, REQ-CAL-02-04, REQ-CAL-02-07 | Существующие labels сейчас ограничивают scale, но не objective. |
| C108-G01 | qualify | REQ-CAL-02-04, REQ-CAL-02-06 | Primal fixtures не доказывают gradient/optimizer/report route. |

## 4. Нормативные требования результата

**REQ-CAL-02-01.** Для конечной observed/training опоры с представимым масштабом _compute_scale_local должен вернуть конечную статистику выбранного scale-профиля, а не epsilon вследствие переполнения промежуточной редукции.

**REQ-CAL-02-02.** Measurement-aware fit должен включать в sample measure только разрешённую обучающую опору существующего split contract; изменение validation/test/holdout values не должно менять training objective при фиксированных train/parameters/scale.

**REQ-CAL-02-03.** Preflight support и objective должны использовать одну effective fit mask: target без неё помечается no-effective-fit-support, а отсутствие опоры у всех targets прекращает оптимизацию до шага, сохраняя допустимые независимые targets и данные оценки.

**REQ-CAL-02-04.** Fit, GradNorm, обе Hessian objectives и final weighted target losses должны потреблять одну training base-vector функцию с priority после sample reduction; penalties не изменяются из-за технического split.

**REQ-CAL-02-05.** Разные формы predicted/observed/quality/split-mask должны отвергаться до неявного broadcasting; добавление placeholder дат другого target не меняет масштаб и training loss неизменного target.

**REQ-CAL-02-06.** На supported JAX execution полностью masked конечный target должен иметь primal0 и reverse-gradient0, включая JIT; partial support сохраняет ненулевой градиент активных элементов, nonfinite prediction остаётся ошибочным.

**REQ-CAL-02-07.** Отчёт должен различать training objective и descriptive/evaluation metrics по validation/test/holdout; full-data fit допускается только при явно выбранной роли, которая не обещает независимой оценки на тех же строках.

## 5. Конкретное техническое решение — рекомендуемый способ

- В calibrator.py::_compute_scale_local сохранять boolean masks/empty handling; привести выбранные значения к host float64 и считать статистику после нормирования на m=max(abs(selected)). Для m>0 работать с bounded selected/m и умножить финальную статистику на m; std — population std с тем же ddof=0. Это предотвращает overflow float32 суммы/квадратов без глобального JAX x64 switch. Проверить representability финального scale; nonfinite arithmetic при непустой конечной опоре выдаёт явную численную ошибку, не no-data epsilon.
- В Calibrator.run measurement branch рядом с уже построенным training_mask создать один frozen per-target fit mask из существующих labels и permitted observation support. Не вводить второй splitter. Использовать quality*fit_mask и в measurement_support, и в _base_vec_from_traces; проверять точные shapes. Хранить сам MeasurementBundle/labels неизменными, чтобы evaluation данные оставались доступны.
- Не переносить priority в quality и не дублировать loss formulas: _forward_evaluation/_target_loss_vec/две Hessian closures остаются на _base_vec_from_traces. Для оценочных partitions использовать тот же pointwise/reducer с отдельно объявленной measure только при формировании descriptive metrics, не в fit objective.
- Для существующих unlabelled inputs сохранить явно документированный legacy all-eligible профиль; для уже размеченных данных default=train. Если нужен optional full-data fit, добавить конкретный typed execution choice в существующий config/report boundary с forward-only compatibility, не молчаливую интерпретацию labels. Сначала проверить actual callers, чтобы не вводить ненужный новый режим.
- Расширить существующие test_cal_02.py/test_loss.py; actual integration colocate с calibration lifecycle/current report tests. Не менять good-shape/zero-support logic ради теста и не возвращать старую ошибку golden baseline.

**Существующие code/test owners:**
- [`src/polisyos/foundry/calibration/calibrator.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py).
- [`src/polisyos/foundry/calibration/loss.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/loss.py).
- [`src/polisyos/foundry/calibration/measurement.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/measurement.py).
- [`src/polisyos/ir/observation/compiler.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/observation/compiler.py).
- [`tests/unit/remediation/test_cal_02.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_cal_02.py).
- [`tests/unit/foundry/calibration/test_loss.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/calibration/test_loss.py).
- [`tests/unit/foundry/calibration/test_calibration_lifecycle.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/calibration/test_calibration_lifecycle.py).

## 6. Локальные проверки — все NOT_RUN

### TEST-CAL-02-01 → REQ-CAL-02-01

**Уровень:** native helper + independent numeric oracle. **Ожидается:** positive + negative + boundary.

**Setup:** float32 [3e38,3e38] mean_abs; [1e20,2e20] std; positive observed/train masks; controls constant0, empty eligible и none.

**Действие:** Вызвать реальный _compute_scale_local; затем real pointwise loss с predicted0.99*observed.

**Oracle:** Mean_abs≈3e38, population std≈5e19, оба конечны и не epsilon; loss конечен. Независимый high-precision/rescaled oracle; rtol=2e-6, atol=0 для ненулевых scale; oracle вычислить float64 на фактически представимых float32 inputs, а не на округлённых десятичных подписях. Empty/zero имеет прежний documented floor/no-support, не fabricated data.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-CAL-02-02 → REQ-CAL-02-02, REQ-CAL-02-07

**Уровень:** compiler → actual objective. **Ожидается:** positive + negative + boundary.

**Setup:** Actual ObservationRecord compiler/splitter создаёт train10 и validation10 на общем axis; прогноз [10,10]; остальные params фиксированы.

**Действие:** Изменить только validation10→30; повторить test/holdout; затем изменить train10→12.

**Oracle:** Training loss и его gradient неизменны при evaluation-only mutation; evaluation metric меняется. Train mutation влияет на objective. Scope/labels/первые bytes не переписываются. Контроль удаления fit mask возвращает C108-P04 loss0→2.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-CAL-02-03 → REQ-CAL-02-03, REQ-CAL-02-06

**Уровень:** native JAX/optax. **Ожидается:** positive + negative + boundary.

**Setup:** MSE: predicted x=[1,2], observed=[0,0], scale=1, sample quality=[0,0], затем [1,0]; reduction=sum(q*(x-y)^2)/sum(q) при ненулевой опоре. Отдельно all-validation target и рядом второй supported train target.

**Действие:** Выполнить existing zero-support grad/JIT witness и tiny real Calibrator preflight/step.

**Oracle:** Zero loss/gradient[0,0]; partial gradient[2,0]. All-no-train — отказ до optax, useful supported sibling допускается по declared policy. NaN prediction не становится 0 ни при нулевом весе.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-CAL-02-04 → REQ-CAL-02-04

**Уровень:** native shared consumers. **Ожидается:** positive + negative + boundary.

**Setup:** Реальный one-step income_tax через compile_program/run_pure_scan: один active agent, income=reported_income=1, government_balance=-0.5, trainable rate r=0.5 с штатными bounds[0,1]; обозначить θ=r−0.5. Два targets одного trace government_balance с observations[1] и [9], kind=mse, relative=False, scale=1, epsilon=1e-8, unit sample quality/train coverage. В float32 denom=fl32(1+1e-8)=1, поэтому L1(θ)=(θ−1)^2 и L2(θ)=(θ−9)^2. Weights[9,1], затем [1,9], зафиксированные на сравниваемом состоянии до GradNorm update. Actual ConstraintRegistry содержит equality agents.reported_income==0, constraint_loss enabled/final/weight6: unchanged trace1 даёт penalty6 независимо от r; prior/aux disabled, Hessian damping0. Не подменять механизм готовым loss-vector.

**Действие:** На фиксированном r=0.5/θ=0 оценить настоящий shared forward, GradNorm component inputs и обе physical-parameter Hessian closures; отдельно native optimizer-u autodiff с реальным bounded bijector. Сверить final-report projection на том же выбранном состоянии; optimizer step и его изменённое состояние проверяются отдельно TEST-CAL-02-06.

**Oracle:** Base vector[1,81], unpenalized90/730, total96/736; physical θ/r gradients−36/−164 и обе undamped Hessians[[20]]. Per-component physical gradients[−2,−18]. У штатного r=sigmoid(u), u=0: dr/du=1/4, d²r/du²=0, поэтому optimizer-u gradients−9/−41, Hessian[[1.25]], component gradients[−0.5,−4.5]; не сравнивать разные координаты как одну derivative. Независимый analytic quadratic oracle обязателен; actual physical forward central second difference с h=1/8 (r=0.375/0.5/0.625, допустимые bounded значения) даёт20 и не имеет произвольного шага/precision. Float32 scalar loss/gradient/Hessian rtol=1e-6, atol=1e-6; finite-difference Hessian rtol=1e-5, atol=1e-5. Проверить actual penalty6, constant trace и zero penalty derivatives, а не только total. Никакого prereturn loss/Hessian fixture; одинаковые objective/weights/fit partition у consumers.

**Seams:** Только входной tiny реальный механизм/наблюдения/ConstraintRegistry и чтение фактического selected state; compile_program, run_pure_scan, loss, penalty, bijector, jax.grad/Hessian и report projection настоящие. Existing test_calibrator_mvp.py test_calibrator_constraint_penalty и runtime fiscal.py/constraints.py подтверждают этот owner route; fixture ещё NOT_RUN.

### TEST-CAL-02-05 → REQ-CAL-02-05

**Уровень:** native boundary/property. **Ожидается:** positive + negative + boundary.

**Setup:** Existing test_cal_02 shape/mask witnesses; A values[10,10], затем A[10,10,0,0] с coverage[1,1,0,0] из добавленного B.

**Действие:** Вектор/столбец, mismatched mask и разрешённые equal-shape arrays; compare A до/после B.

**Oracle:** Ambiguous shapes дают ValueError с expected/actual shapes; A scale10/loss≈0.01 не меняются; valid MSE/Huber сохраняются.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-CAL-02-06 → REQ-CAL-02-02, REQ-CAL-02-04, REQ-CAL-02-06, REQ-CAL-02-07

**Уровень:** shared integration E02-I10-A. **Ожидается:** positive + negative + boundary.

**Setup:** Actual compiler→Calibrator на маленьком StaticBundle/JAX/optax; согласовать CAL-01/03/04 interfaces; tmp actual persistence owner если report сохраняется штатным caller.

**Действие:** Один optimizer step, finite chosen state, real final objective/derivatives/report; fresh consumer читает выданные значения и roles.

**Oracle:** Training objective/weights/scale/support совпадают с фактическим fit; descriptive metrics не названы тем же objective; validation-only mutation не изменяет fitted step. Нельзя заменить _execute_forward/jax.grad/optax ожидаемыми fixtures.

**Seams:** Фиксированные synthetic observations/model допустимы; настоящий run_pure_scan/JAX/autodiff/optimizer/report consumer обязательны для native claim.

## 7. Совместная приёмка, зависимости и владение

Общие сценарии: **E02-I10-A, E02-I10-B** из [канонического lane integration-контракта](../03_Интеграция/LANE-10.md). Они переиспользуются; отдельный тяжёлый harness этого пакета не создавать.

Исходные предшественники: CAL-01. Доказанный существующий контракт может удовлетворить зависимость; lane не глобальный барьер.

Один writer на общий calibrator.py; CAL-03/04/06 согласуют тот же base-vector/selected-state contract. CAL-01 предоставляет alignment/split, CAL-02 не правит его семантику. Freeze changed numerical owners перед общим native wave.

## 8. Совместимость и восстановление

Historical reports/observation bytes не пересчитывать. Новые training-only results получают фактический input/policy binding; старые full-data results остаются читаемыми с прежней квалификацией. При forward rollback не включать прежнюю утечку автоматически: удержать новый fit unavailable для affected profile либо явное старое ограничение, сохраняя independent outputs.

## 9. Free-grow и design decisions

- [design_direction §2.2, §4](../05_Основания/Исследование/design_direction.md): переносимый общий reducer/mask, не hardcoded target/domain. Новая fit роль допустима только с явным смыслом.
- North Star §2 и TA D2.5: conditional model fit полезен до empirical authority; tiny native test не сертификат реального мира.
- Исходный repair не расширяется до автоматического изобретения модели или полной statistical calibration.

- [North Star §2](../05_Основания/Архитектура/policy-design-causal-operating-system-north-star.md#2-everything-reduces-to-data--but-the-causal-structure-is-not-data) и [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md#d25-epistemic-regime-architecture): общий механизм не доменная ветка; conditional fit не равен подтверждённому causal effect.

## 10. Решения, которые нельзя подменить догадкой

- DEC-CAL-02-01: проверить callers unlabelled и явно full-data calibration. Выход — конечная таблица supported fit-role→source labels→report meaning. Если full-data caller отсутствует, не строить новый режим; если есть, согласовать named profile, не скрывать train/validation leakage. Это не блокирует scale fix.

## 11. Что предъявить и что не является готовностью

Предъявить before/after R01/R02, native grad/JIT/step и общий objective witness; проверить all-no-support и полезный partial-support. Не выдавать 13 старых NumPy fixture PASS за JAX, совпадение primal за Hessian, finite0 за наблюдения, изменение validation data за независимое обучение. Закрытие G01 требует реальной supported среды, не копии тела функции.

**Команды:** из `policy-engine/` использовать существующее поддержанное Python 3.14 окружение и точные существующие test paths выше. Шаблон: `<existing-python> -m pytest <selected-existing-path> <new-selector-after-authoring>`; это не выполненная команда и не утверждение, что будущий selector уже существует. Native job — один по общему ресурсу. Никаких install/full-suite по умолчанию.

## 12. Полнота inventory-трассировки

### Оставшиеся обязанности

- `remaining:0301` → REQ-CAL-02-01. Воспроизведён overflow finite float32 scale.
- `remaining:0302` → REQ-CAL-02-02, REQ-CAL-02-03, REQ-CAL-02-04, REQ-CAL-02-07. Существующие labels сейчас ограничивают scale, но не objective.
- `remaining:0303` → REQ-CAL-02-04, REQ-CAL-02-06. Primal fixtures не доказывают gradient/optimizer/report route.
### Сохранение

- `preserve:0456` → REQ-CAL-02-05 → TEST-CAL-02-05. Exact shape checks — проверяется указанным конкретным positive/boundary oracle, не только наличием текста.
- `preserve:0457` → REQ-CAL-02-04 → TEST-CAL-02-04, TEST-CAL-02-06. Sample quality отдельно от target priority — проверяется указанным конкретным positive/boundary oracle, не только наличием текста.
- `preserve:0458` → REQ-CAL-02-06 → TEST-CAL-02-03. Safe inactive denominator — проверяется указанным конкретным positive/boundary oracle, не только наличием текста.
- `preserve:0459` → REQ-CAL-02-03, REQ-CAL-02-06 → TEST-CAL-02-03, TEST-CAL-02-06. Finite guard и no-support status — проверяется указанным конкретным positive/boundary oracle, не только наличием текста.
- `preserve:0460` → REQ-CAL-02-01, REQ-CAL-02-02, REQ-CAL-02-05 → TEST-CAL-02-01, TEST-CAL-02-02, TEST-CAL-02-05. Observed/training frozen scale — проверяется указанным конкретным positive/boundary oracle, не только наличием текста.
- `preserve:0461` → REQ-CAL-02-04, REQ-CAL-02-07 → TEST-CAL-02-04, TEST-CAL-02-06. Shared base-vector consumers — проверяется указанным конкретным positive/boundary oracle, не только наличием текста.
