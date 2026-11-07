# LANE-10: общий интеграционный контракт

**Цель:** Калибровка оптимизирует объявленную цель, uncertainty сохраняет совместный закон, а DOE/robustness не улучшают вывод удалением неудобных наблюдений.

Состояние проверок: **NOT_RUN**. Это обязательные критерии будущей связанной приёмки, а не свидетельство текущего PASS. Семейство запускается один раз для согласованного изменения; локальные packet tests не дублируют его инфраструктуру.

## Область и зависимости

Пакеты: CAL-02, CAL-03, CAL-04, CAL-06, UQS-01, UQP-01, UQP-02, UQP-03, DOE-01, DOE-02, DOE-03, STR-01

- CAL-02 получает CAL-01 из LANE-07; CAL-06 зависит от CAL-04/UQP-02, UQS от UQP-02/CAL-06.
- DOE/STR исходно CP3, CAL/UQ — CP4: не превращать lane в один пакет или один барьер.

## Профиль и допустимые подмены

- **P-CORE:** policy-engine Python >=3.14,<3.15; actual project lock/extras, supported existing environment; imports bind tested checkout/artifact (основание: policy-engine/pyproject.toml:8)
- **P-JAX:** P-CORE + locked base JAX/jaxlib/optax; deterministic CPU tiny mechanism unless selected accelerator explicitly required; no invented XLA flags (основание: policy-engine/pyproject.toml; AGENTS.md)
- **P-ANALYTICS:** P-CORE + applicable analytics/causal-core extras and exact selected numeric backend; no fixture substitution for native numeric claim (основание: policy-engine/pyproject.toml [project.optional-dependencies])
- **P-SENSITIVITY:** P-CORE + sensitivity extra SALib>=1.5,<2.0 with resolved lock version and scipy; real accepted design/block semantics (основание: policy-engine/pyproject.toml sensitivity)

- Малый настоящий differentiable mechanism и заранее известный joint law; fixed seeds/data — test fixtures, не empirical calibration.
- Sampler spies допустимы для передачи kwargs; один реальный JAX/SciPy/SALib selected path нужен для native claim.
- Нельзя выключать folds/draws/ошибки или менять product policy ради зелёного smoke.

Подмена запрещена для принимаемого свойства: если проверяется запись/чтение, actual store и fresh reader обязательны; если численный метод — actual backend; если physical cleanup — actual OS resource. Внешний provider/encoder может быть лёгким и контролируемым, когда качество модели/сети не входит в claim.

## Подготовка и порядок

1. На выбранном поддерживаемом профиле связать checkout/build SHA и входные fixtures. Использовать существующие test owners ниже, прочитать их реальные seams перед расширением
2. Выполнить локальные REQ/TEST затронутых пакетов, затем каждый применимый вариант этого семейства. Независимые варианты допускают раздельный запуск
3. Положительный прогон должен пройти actual producer→передача/хранение→fresh consumer. При отсутствии хранения в конкретном алгоритме проверить непосредственный downstream consumer, не придумывая CAS ради отчётности
4. Повторить адресный негативный/граничный контроль. Изменение одного deciding input или отключение исправленного механизма должно менять наблюдаемый исход; unrelated пригодный результат остаётся доступным
5. Сохранить входы, события/значения/ошибки, ref identities, численные tolerances и команды. Итог связывает покрытые REQ, а не только список пакетных имён

## E02-I10-A — Targets → differentiable calibration → report

Покрываемая область: CAL-02, CAL-03, CAL-04, CAL-06

**Положительный oracle:** На маленьком actual mechanism веса 9:1→1:9 меняют ожидаемую цель; final loss/components/series от одного состояния/forward. Multi-start выбирает finite qualified результат; tied covariance сохраняет rank. Для shared derivative oracle: один реальный скалярный параметр θ, L1=(θ−1)^2, L2=(θ−9)^2, θ=0, постоянный penalty6, unit scale; веса9:1/1:9 дают total96/736, gradients−36/−164 и Hessian20 для обоих. Градиенты и Hessian здесь заданы в physical θ; optimizer-u вычисляется по фактическому bijector/chain rule, не сравнивается как та же координата. Подробный исполнимый fixture — TEST-CAL-02-04 (θ=r−0.5, r=sigmoid(u): при u=0 gradients−9/−41, Hessian1.25). Привязать к фактическому differentiable producer, не подставлять готовые losses. Fit support нейтрализует excluded observation/residual operands ДО нелинейных square/Huber/AD операций. При fixed training/model/scale actual float32 heldout10→3e38 сохраняет training primal, gradient, Hessian и один native Optax update eager/JIT; evaluation-range limitation отделена от fit.

**Различающий негативный oracle:** Empty support не получает good fit; overflow/split-to-objective mismatch и unselected target gate не искажают выбранную цель. Display 0.8/0.95 не меняет conditional sigma; failed start не скрывает useful sibling. Where над уже вычисленным inf loss недостаточен. Полностью masked цель даёт zero contribution только при наличии допустимого fit support другой цели; весь empty corpus остаётся no-fit. Отдельный прежний nonfinite model-prediction guard не ослабляется.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I10-B — Joint law → delta/MC → persisted uncertainty

Покрываемая область: UQS-01, UQP-01, UQP-02, UQP-03

**Положительный oracle:** Correlated inputs + fixed constant дают known linear result; covariance representation и batch size сохраняют предмет. Empirical atoms/weights/shared rows/asymmetric draws доступны consumer; duplicate ref не усиливает precision. Finite binary64 point mean использует общий тонкий FED/UQS owner над CPython3.14 statistics.mean; независимый Fraction oracle проверяет числа, не вызывает тот же owner.

**Различающий негативный oracle:** Zero std не получает искусственный noise; absent output остаётся unavailable, не zero; rejected/filtered draws не превращаются в unconditional full law. Same-input retry bounded; changed basis не reuse старую curvature.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I10-C — Source-bound design → evaluation → sensitivity/stress

Покрываемая область: DOE-01, DOE-02, DOE-03, STR-01

**Положительный oracle:** План на разных диапазонах/законах связывает samples/block identities/seeds и все costs; known effects согласованы с единицами; top-k не меняет score/worst-case. Full-request RNG isolation включает PCA: actual sklearn1.8.0 resolved solver/profile и explicit local derived seed сохраняются до fresh readback. Bounded 600×100,k5 randomized-branch witness использует deterministic compatible model, two-parameter Morris200,num_levels8 и проверенный centered rank>15; AB/BA/replay не читают и не меняют ambient NumPy state.

**Различающий негативный oracle:** Failed row не теряется при scalar/multi-output или median fill; block/trajectory integrity проверяется до SALib. Unsupported law отказывает явно; unavailable scenario не считается valid и не улучшает denominator. Tiny deterministic PCA branch недостаточен; не force full SVD на всех размерах и не сравнивать signs/tied eigenvectors. Independent projector/reconstruction oracle и measured cost остаются отдельны; seeded FAST pending не закрывается исправлением PCA.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## Существующие места расширения tests

Список означает проверенные пути, не доказательство полноты или запуска всего содержимого. Новые проверки добавлять к ближайшему владельцу; отдельный harness создавать только при реальном разрыве.

- [policy-engine/tests/unit/foundry/calibration/test_calibration_lifecycle.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/calibration/test_calibration_lifecycle.py) — SHA256 `8662008e66ab9e92d1f4d3115d4ceba11459894b41d201b2b1e83424b0079acf`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/remediation/test_cal_04.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_cal_04.py) — SHA256 `31b7b6afb4e3e8587865c168ad8953ba0138271737185633df3400a351ebe4f7`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/calibration/test_calibration_uncertainty_adapter.py) — SHA256 `2ece8527030a089ef40515aa11c5ca5b993b185eb6fd04089bf0461ad83f11ba`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_propagate_uncertainty.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_propagate_uncertainty.py) — SHA256 `da9d8c7732027064b3bf4b690fe8e75551761f9ad2b399bd9f6c71cede689e8a`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/foundry/uncertainty/test_monte_carlo_b194.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/uncertainty/test_monte_carlo_b194.py) — SHA256 `56b5275b2227686e261639002aca3094d529c71ce52f442c62b76f6153f9e8f1`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/remediation/test_doe_02.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_doe_02.py) — SHA256 `cce40927263a910511d0acb2f1eec461539d9900e5a6c6df26982edff26ef03f`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/scientist/search/test_adversarial_direction_c49.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/search/test_adversarial_direction_c49.py) — SHA256 `c4a7114101ddbccd46b5c4d25dbb138044fc12f066e92137b1e3f8ed11d7fdf6`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.

## Выход приёмки

- Один manifest исполнения семейства: base/head SHA, scenario-ID, связанные REQ/TEST, профиль, входы и их hash, actual commands/exit, фактические positive/negative oracles, ограничения
- Перечень doubles с объяснением, какое свойство ими не проверяется
- Для failure/unknown: точная стадия и сохранённый полезный результат. Не перекрашивать BLOCKED/UNRUN в PASS
- Ремонт механизма и предметная валидность имеют разные решения. Синтетический механизм может пройти, не подтверждая прогноз/каузальную идентификацию/мандат реального кейса
