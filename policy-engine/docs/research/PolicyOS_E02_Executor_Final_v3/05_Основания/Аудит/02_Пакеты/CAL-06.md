# CAL-06 — tied coordinates, covariance и неизменный conditional scale

**C111 · LANE-10 · B197, B198 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

Оба основных ремонта содержательно присутствуют. Calibrator строит явную matrix projection из групповых координат к node.field, report валидирует basis/coverage, adapter вычисляет `J Σ Jᵀ`. Tied поля не превращаются в независимые свидетельства: actual Gaussian joint consumer сохраняет singular covariance. Hessian envelope несёт typed Normal mean/std отдельно от отображаемой heuristic band; изменение display level не меняет условную sigma и не повышает authority.

**Остаток C111-R01:** explicit trainable subset с не назначенным handle заставляет producer отказаться от всей projection, включая полезную covariance уже выбранных tied полей. **C111-G01:** native optimizer/CAS/full propagation не квалифицированы.

**4 MATCH; 13 неизменённых test bodies / 14 cases PASS в bounded runner.** Это не native suite и не empirical/inferential validation.

## 2. Матрица исходных оснований

| ID | Исходный ремонт | Фактическая способность | Остаток |
|---|---|---|---|
| B197 | Явный coordinate map, covariance projection, exact coordinate order и field coverage вместо строкового угадывания. | A.rate/B.rate получают variance/cross-covariance 0.0025, rank 1. Переименование shared group не меняет результат. Incompatible bounds отвергаются. | R01: unrelated unassigned C.rate приводит к incomplete и потере A/B envelopes. Native producer/persistence G01. |
| B198 | Typed ParametricFitCarrier задаёт mean/std; covariance consumer предпочитает его mutable metadata и display width. | Existing STD=1 остаётся 1 при levels .8/.95; отдельный JSON roundtrip STD=.05 также неизменен. Missing/incomplete law не получает fake scale. | G01: full persistence/propagation не исполнены; legacy carrier-less interval fallback не объявлен универсальным законом. |

## 3. Producer → consumer

Actual group resolver связывает refs по точному handle identity, объединяет bounds и сохраняет group indices [S01:2020–2107](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py#L2020-L2107). Для скалярных групп producer строит строки one-hot, поэтому двум tied полям соответствуют две строки [1]. Report сохраняет field order, coordinate order и matrix; adapter проверяет совпадение uncertainty basis и проецирует covariance [S03:364–384](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py#L364-L384).

Envelope получает typed Normal parameters и остаётся `HEURISTIC_RANGE`, `confidence_level=None`, `is_heuristic_ci=True`, `gate_eligible=False`. Display level сохраняется лишь как requested metadata. `extract_std` сначала читает типизированный law, а не ширину полосы [S04:27–81](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/covariance.py#L27-L81).

Actual selected Gaussian joint builder вызывает full covariance с `preserve_singular=True`, затем факторизует её [S06:585–637](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py#L585-L637). P02 доходит до этого consumer, а не заканчивается наличием metadata. Полный MonteCarloPropagator не запускался.

## 4. Выполненные проверки

| Проверка | Результат |
|---|---|
| P01 | 5 CAL-06 bodies / 6 cases и 8 adapter bodies: 14 PASS. Typed scale, mutable metadata, incomplete law, uniform support, missing STD, v1/v2 boundaries, renamed ties. |
| P02 | Actual selected resolver→projection→DTO→adapter→covariance→joint spec: matrix всех элементов 0.0025, rank 1; external draw control даёт одинаковые tied значения. Gates false. |
| P03 | Добавлен C.rate, не выбранный refs: group covariance остаётся, projection incomplete, envelopes 0 вместо 2. |
| P04 | Display .8/.95 меняет width, но JSON roundtrip сохраняет std .05, heuristic и запрет gate. Несовместимые bounds дают ValueError. |

[Probe](../04_Проверки/C111_CAL06/probe_cal06.py) · [diagnostics](../04_Проверки/C111_CAL06/bounded_diagnostics.json) · [команды/логи/exit codes](../04_Проверки/C111_CAL06/commands.json).

Selected DTO bodies и validators не изменены. `jnp=NumPy`, fixture handles/state и reference-only Any bindings объявлены. JSON roundtrip не выдаётся за native CAS wire proof. Run01 содержит внешнюю syntax error до исполнения; run02 исправляет только внешний harness, исходник репозитория не менялся.

## 5. C111-R01 — all-or-nothing projection теряет полезную частичную работу

При explicit refs resolver создаёт группы только для выбранных handles. Другие значения сохраняются в base state, но final `calibrated_params` перечисляет все handles [S01:3305–3311](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py#L3305-L3311). Projection требует назначения **каждого** handle и при одном unassigned поле возвращает только incomplete diagnostic [S01:3514–3533](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/calibration/calibrator.py#L3514-L3533). V2 adapter без projection безопасно не угадывает имена, поэтому исчезают и пригодные A/B envelopes.

P03 использует actual resolver и exact projection statements: A/B refs tied в shared_rate, covariance группы 0.0025. Добавлен C.rate вне refs. Report содержит все три point values и ту же group covariance, но статус incomplete и 0 envelopes. Контроль без C даёт 2 envelopes. **Это availability/partial-result loss, не false scientific authority:** отказ явный, covariance не уничтожена в report, неизвестная uncertainty C не выдумана.

**Оставшаяся работа:** согласовать producer report scope и existing projection contract для ограниченного подтверждённого uncertainty scope. Отличить просто сохранённые значения от действительно оценённых полей либо представить validated partial projection явно. Не снимать complete/basis guards, не угадывать mapping по имени, не приписывать C нулевую дисперсию без основания. Полный optimizer не выполнялся; вывод ограничен actual selected producer/consumer chain.

## 6. Сохранить и доквалифицировать

Сохранить explicit matrix/basis, covariance cross-terms, singular null space, bounds refusal, отсутствие fake STD, typed-law precedence и все heuristic/gate restrictions. Точная shared coordinate — одна степень свободы, не два независимых подтверждения. Conditional Hessian Normal approximation не становится полноценным posterior только из-за typed carrier.

C111-G01: нужны supported-runtime calibration→persist/load→propagation проверки, общие для LANE-10/UQP при подходящем существующем fixture. Native calibration/adapter/covariance/IR imports здесь BLOCKED на Python 3.14-only syntax `uncertainty.py:287`; JAX/pytest отсутствуют. Ничего не устанавливалось. Artifact-reference annotations в выбранном report setup не проверяют CAS admission; tested fields/validators основные реальные.

Legacy carrier-less fallback продолжает вычислять эвристический scale из width; текущий typed Hessian route его не использует. Это не доказательство универсального Normal-law для произвольной полосы. Более широкие UQP consumers и Bayesian adapter routes будут рассмотрены в собственной очереди; original predecessor UQP-02 не отмечен завершённым заранее.

[Исходная карточка](../05_Источники/CAL-06_исходные_строки.txt) · [pinned sources](../05_Источники/C111_источники.json) · [остатки](../01_Реестры/C111_остатки.json) · [точные границы](../04_Проверки/C111_CAL06/Чтение_и_границы.md).

**111/127 — промежуточный аудит. Следующий UQS-01. Фаза заданий исполнителю не начата.**
