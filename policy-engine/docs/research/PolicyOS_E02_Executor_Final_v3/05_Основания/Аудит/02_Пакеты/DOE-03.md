# DOE-03 — целые блоки, failure-policy, PCA и шкала Morris

**C118 · LANE-10 · B102–B105 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

Основные ремонты работают: DROP_FAILED исключает целые Morris trajectories, а не склеивает surviving rows; scalar и multi-output применяют одну policy до PCA и сохраняют исходный знаменатель; оба PCA backend ограничены centered-rank cap; Morris uncertainty использует normalized coordinate effects и отказывает при неизвестной конвенции.

**6 MATCH; 3 unchanged test bodies PASS. C118-R01 остаётся:** explicit median imputation сохраняет failed counts, но ordinary uncertainty получает `ok` без qualification модели восстановления. Настоящие NumPy/sklearn/percentile bootstrap выполнены; SALib point — явный fake boundary. Полного native/scientific закрытия нет.

## 2. Матрица исходных оснований

| ID | Исходный ремонт | Actual capability | Остаток |
|---|---|---|---|
| B102 | Whole blocks, IDs/reasons и ограниченность после отбора. | Из12 rows удаление [1] оставляет trajectories [1,2,3], удаление [1,4,5] — [2,3]. Geometry проверяет coordinate changes, не только делимость. | R01 для imputation; G02 для source identity/selection mechanism. |
| B103 | Общая failure-policy до PCA и original accounting. | FAIL_FAST/min_success_rate одинаково останавливают scalar/multi до backend; explicit imputation сохраняет N=12, success=9, failed=3. | R01: counts сами по себе не квалифицируют uncertainty на invented values. |
| B104 | Допустимый PCA rank и честный variance threshold. | 3×5 допустима в actual sklearn и NumPy SVD, не более2 компонентов; нулевой public input отказан; cap1 показывает unmet_limited. | Scientific sufficiency явно not_established; G01/G02. |
| B105 | Одна normalized шкала effects и UQ. | Actual effects и bootstrap invariant при input-unit changes; output×1000 масштабирует estimate/CI×1000. Retained JSON повторяет точный CI. | Native SALib point comparison не выполнен; transformed-coordinate UQ conservatively unavailable. |

## 3. Producer → consumer

[Preparation owner](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/analysis.py#L180-L320) фиксирует failed row reasons, исходные/effective trajectory IDs и limited selection posture. [Multi-output owner](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/multi_output.py#L86-L173) передаёт preparation context в каждый component **до** uncertainty, затем сохраняет counts и PCA metadata. Исправление не сводится к косметическому исправлению total_runs после вычислений.

[Centered-rank selection](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/multi_output.py#L175-L215) применяется до выбора sklearn/SVD. Широкая малая матрица больше не становится недопустимой из-за установки sklearn; unmet quality threshold не объявляется достигнутым.

[EE owner](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/uncertainty.py#L451-L529) требует physical bounds/grid и делит output change на normalized coordinate delta. Это согласованная конвенция ordinary ungrouped uniform Morris, не универсальная коррекция для произвольных transformed/scaled designs. Actual storage/restore и percentile bootstrap потребляют ту же матрицу.

## 4. Проверки

| Проверка | Результат |
|---|---|
| P01 | 3 unchanged bodies PASS: real sklearn, real NumPy fallback и coordinate-contract refusal. |
| P02 | Whole-block IDs/counts и отказ malformed geometry; никакой склейки survivors. |
| P03 | Scalar/multi policy parity, original denominator и preserved failed counts. |
| P04 | Обе PCA реализации согласны на 3×5 и 3×2; public zero-variance refusal; unmet_limited при binding cap. |
| P05 | 24 synthetic trajectories: normalized estimate25 и CI≈[24.2986,25.5556] для трёх input units; output×1000 масштабирует их×1000. Exact DTO JSON replay. Не coverage experiment. |
| P06 | 1 failed row из48: DROP_FAILED → limited/unavailable; IMPUTE_BASELINE → actual bootstrap и all ci_status=ok без imputation limitation. |

[Probe](../04_Проверки/C118_DOE03/probe_doe03.py) · [actual imputed result](../04_Проверки/C118_DOE03/run01/imputed_result.json) · [diagnostics](../04_Проверки/C118_DOE03/bounded_diagnostics.json) · [команды](../04_Проверки/C118_DOE03/commands.json).

## 5. Остаток и сохраняемое поведение

**C118-R01 — unqualified UQ после median imputation (medium).** [IMPUTE_BASELINE](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/analysis.py#L298-L320) заменяет отсутствующее значение медианой observed outputs; [Morris attachment](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/analysis.py#L352-L387) ограничивает DROP_FAILED, но не этот случай. В P06 actual bootstrap получает изменённую матрицу и возвращает обычное `ok`. Отдельная missingness/imputation model не задана, дополнительная неопределённость не учитывается. Failed count **не потерян**, и downstream gate bypass **не доказан**. Дефект узкий: неподтверждённое UQ promotion, а не само разрешённое exploratory заполнение. Сохранить полезный provisional result, но ограничить authority/CI до квалификации существующим owner.

**C118-G01/G02.** Native SALib point и полный persisted/fresh consumer ещё не запускались. Fake point=1 в probe не сравнивается с genuine bootstrap estimate как product defect. Geometry и positional IDs не аутентифицируют original design. Whole-block dropping не исправляет selection bias; PCA admissibility не делает три observations научно достаточными. Сохранить все текущие guards, limited metadata и original counts; расширять существующие связи, не изобретать второй DoE.

[Исходная карточка](../05_Источники/DOE-03_исходные_строки.txt) · [источники](../05_Источники/C118_источники.json) · [остатки](../01_Реестры/C118_остатки.json) · [границы](../04_Проверки/C118_DOE03/Чтение_и_границы.md).

**118/127. Следующий STR-01; LANE-10 ещё не завершён. Фаза заданий исполнителю не начата.**
