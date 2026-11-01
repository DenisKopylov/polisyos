# UQP-02 — covariance, совместный закон и empirical carrier

**C114 · LANE-10 · B187, B188, B192 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

Основной ремонт содержательный: covariance rows остаются у своих envelopes, переставляются только именованные columns; матрица проверяется до численной обработки. Analytical использует `wᵀΣw`, delta и оба MC transforms сохраняют Gaussian null space. Empirical samples/weights/row axis действительно потребляются, не заменяются CI-derived Normal. Неизвестная/несовместимая связь не становится независимостью.

**6 MATCH; 11 неизменённых bodies / 11 cases PASS.** Actual SciPy Sobol и inverse CDF выполнены; NumPy PRNG и finite-difference derivative — явные seams, не native JAX. **Остатки:** std0 искусственно превращается в шум (**R01**), empirical clipping теряет малую крайнюю массу (**R02**). Native successful report/CAS и scientific authority остаются **G01**.

## 2. Матрица исходных оснований

| ID | Исходный ремонт | Actual capability | Остаток |
|---|---|---|---|
| B187 | Именованные axes перед repair. | Диагонали1/9 сохраняются; все6 перестановок трёх координат с diag1/4/9 и cross terms дают исходную матрицу. Duplicate/mixed axes, mismatch, asymmetry, indefinite matrix отвергаются. | Native numeric profile G01; нельзя заменять full covariance диагональю. |
| B188 | Один joint law для backend. | a=b, y=a−b: analytical/delta variance0, random/Sobol loop difference0. Independent numerical control variance2, но не новый authority proof. | R01: marginal degenerate Normal отличается от того же закона с explicit zero covariance. Scientific joint admission G01. |
| B192 | Exact empirical law используется повторно. | Atoms−1/0/1, masses9:1, shared row indices и axis сохраняются; incompatible axes/weights/lengths/mixed carriers дают typed refusal. | R02: empirical endpoint clipping; full persisted re-propagation/native JAX G01. |

## 3. Producer → consumer

Covariance contract определяет owner row именем envelope. После column reorder проверяются dimensions, unique names, marginal diagonals, symmetry и PSD; `preserve_singular=True` не добавляет jitter в исходный law [S01:121–242](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/covariance.py#L121-L242). Analytical заново восстанавливает named matrix и отвергает несовпадающий caller-supplied covariance, затем использует quadratic form [S02:61–108](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/analytical.py#L61-L108).

Общий preparation owner разрешает empirical/Gaussian law до evaluator binding. Gaussian spec сохраняет means/full factor; empirical spec требует согласованные axis/count/weights и declared joint ID для нескольких columns [S03:586–733](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py#L586-L733). Actual public refusal paths выполнены. Successful random loop использует одни shared indices для всех empirical columns, QMC использует одну uniform coordinate. Наличие общего ID остаётся **declared_non_authoritative**, не доказательство происхождения.

Dispatcher направляет typed carriers к law-aware MC, не подставляет envelope summary moments в analytical/delta. No-carrier multivariate numerical control не превращается в установленную независимость: gate cap сохраняется. Полного закона для произвольной nonlinear зависимости одна covariance не доказывает.

## 4. Выполненные проверки

| Проверка | Результат |
|---|---|
| P01 | 11 existing bodies PASS: axes, analytical dispatcher, delta, empirical incompatibility и unknown-dependency refusal. |
| P02 | 6 permutations трёх осей; cross terms сохранены. Три malformed controls отвергнуты; jitter10 не делает indefinite law допустимым. |
| P03 | Shared Gaussian null space: analytical0, delta0, оба128-draw loops difference0; independent formula control2. Gates false для multivariate outputs. |
| P04 | Atoms и shared empirical rows сохранены. Negative fraction при masses9:1: .8828125 в NumPy-random control, .90625 в actual Sobol128. Это finite numerical controls, не coverage. DTO JSON roundtrip сохраняет carrier. |
| P05 | std0 admitted, marginal transforms добавляют ±1e-12. Actual loop/evaluator для 1[a>0]: .5546875 random-control/.4921875 Sobol, explicit zero-covariance control0. |
| P06 | Weights(1e-12,1−1e-12): uniforms0/5e-13 дают второй атом+1 вместо первого−1 из-за clipping. |

[Probe](../04_Проверки/C114_UQP02/probe_uqp02.py) · [diagnostics](../04_Проверки/C114_UQP02/bounded_diagnostics.json) · [команды/логи/exit codes](../04_Проверки/C114_UQP02/commands.json).

## 5. Подтверждённые ограниченные остатки

### C114-R01 — point mass получает искусственную дисперсию

Typed Normal std0 разрешён `_normal_parametric_fit`. Но marginal random и QMC transforms используют `max(std,1e-12)` [S03:2572–2585](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py#L2572-L2585), [S03:2662–2669](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py#L2662-L2669). Тот же law с явной covariance[[0]] проходит singular factor и остаётся точно0.

Величина искусственного шума мала, но функционал может быть пороговым: actual loops/evaluator recorder для `1[a>0]` получают ненулевые ответы там, где point mass0 всегда даёт0. Native JAX random и downstream report/gate не выполнялись; SciPy QMC transform и actual loop выполнены. **Оставшаяся работа:** сохранить точечный law в обеих marginal ветках и проверить согласованность с существующим singular path, а не расширять std без явной модели ошибки.

### C114-R02 — Gaussian-style clipping не подходит empirical inverse CDF

`_empirical_indices_from_uniform` ограничивает u диапазоном [1e-10,1−1e-10] [S03:788–796](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py#L788-L796). В отличие от непрерывной Normal inverse CDF, empirical carrier имеет конечные крайние атомы. Допустимая масса1e-12 исчезает для u=0 и5e-13. Actual carrier/admission сохраняют эту массу, теряет её именно consumer index mapping.

Нужно разделить endpoint conventions finite empirical law и защиту от Gaussian infinities, сохранив shared indices и веса. Это узкий редкий numerical boundary; частота в пользовательских данных и QMC convergence не измерялись.

## 6. Сохранить и доквалифицировать

Сохранить named axes, запрет concealment через spectral repair, singular null space, typed-law precedence, empirical atoms/weights, shared indices, partial numerical usefulness и non-gating qualification. Ни повторное sampling, ни joint metadata не создают новые наблюдения/доказательства независимости.

**C114-G01:** supported-runtime native JAX random, full successful result builder, CAS roundtrip/re-propagation и selected posterior profile ещё не квалифицированы. Здесь actual common admission/analytical/refusal routes и successful loops до buffers; не весь MonteCarloPropagator. SciPy1.17.0 и NumPy2.3.5 настоящие; заменённый PRNG не JAX PRNG, numerical Jacobian не autodiff, DTO JSON не CAS. Native imports BLOCKED на3.14 syntax в Python3.12.14, pytest/JAX отсутствуют. Scientific validity требует отдельного основания, не названия Normal или Bayesian.

[Исходная карточка](../05_Источники/UQP-02_исходные_строки.txt) · [pinned sources](../05_Источники/C114_источники.json) · [остатки](../01_Реестры/C114_остатки.json) · [границы](../04_Проверки/C114_UQP02/Чтение_и_границы.md).

**114/127 — промежуточный аудит. Следующий UQP-03. Фаза заданий исполнителю не начата.**
