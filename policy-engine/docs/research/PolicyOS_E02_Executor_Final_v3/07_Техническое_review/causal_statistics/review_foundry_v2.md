# Независимое peer-review foundry_numeric proposed v2

**Вердикт: принять проверенную редакцию спецификаций после `peer_delta_01`. Открытых блокирующих замечаний нет. Native/product tests — NOT_RUN.** Это согласование технического задания и его oracle, не утверждение об исправлении продукта или прохождении квалификации.

## Объём и независимость

Полностью прочитаны предложенные MD и семантически все поля JSON шести пакетов: CAL-02, BKT-02, UQS-01, PLG-03, DOE-02, DOE-03; **33 REQ / 31 TEST**. Прочитаны фактические baseline→proposal изменения всех шести пар и трёх обзоров LANE-03/04/10. JSON проверен не только синтаксически: все requirement text и test setup/action/oracle сопоставлены с прочитанным MD, остальные несовпадающие текстовые поля просмотрены отдельно. Восстановлены первоначально обрезанные части вывода. Полное повторное чтение всех неизменённых baseline-байтов не заявляется.

Для каждого из **15 файлов** независимо вычислены baseline/proposed SHA-256, проверены manifest hashes и сохранённые unified diffs против вновь построенных actual diffs. Все прежние ID, source/residual/obligation/preservation maps, dependencies и shared bindings сохранены. Точные полные hashes, диапазоны чтения и источники находятся в [`review_foundry_v2.json`](review_foundry_v2.json). Общие 03 и aggregate 04 не входят в это согласование.

Авторские findings/manifest рассматривались как утверждения, а не доказательство. Проверен действительный код immutable HEAD `20d9009be21097bfbdc38a546a15cc60213b8ace`. Дополнительно выполнена только независимая stdlib-арифметика: [`review_foundry_arithmetic.py`](review_foundry_arithmetic.py), [результат](review_foundry_arithmetic.json). Repository imports, NumPy/JAX/SALib/sklearn execution, product tests, установки и изменения продукта/proposal не выполнялись.

## Найденное и закрытое замечание

**CS-FN-PEER-01 — PLG value/entropy oracle, medium; RESOLVED.** В первоначально проверенной редакции новая REQ-PLG-03-02 обещала проверку policy/value/entropy, но analytic case устанавливал оба коэффициента в ноль. Реализация с удалённым value либо entropy term прошла бы этот oracle. Этот пробел независимо подтверждён здесь; runtime/root peer сообщил тот же результат. Не объявляется новое отдельное замечание к уже исправленным байтам.

Авторская адресная поправка прочитана в фактических MD/JSON. Дополнены шесть ненулевых separate/combined coefficient controls, actual `critic_out.bias[0]=ν`, actual `action_log_std[0]=ℓ`, fixed returns `[1,3]`, fixed advantages `[0,0]`. При ν=ℓ=0:

- raw value loss = `(1²+3²)/2 = 5`;
- raw entropy `H0 = (1+ln(2π))/2 = 1.4189385332046727`;
- total `5cv − ce H0`, gradients `dL/dν=−4cv`, `dL/dℓ=−ce`.

В actual `rl.py` **нет дополнительного множителя 1/2** у squared value loss. При ℓ=0 log-std clipping неактивен; реальные архитектурные координаты существуют. Нулевые fixed advantages не требуют дифференцирования их нормализации по actor fields. Коэффициенты сравниваются в фактически представимых float32 значениях. Separate/combined пары различают пропуск, знак и игнорирование коэффициента; исходные policy cases сохранены. Итоговые hashes:

- PLG-03.md: `bdc3c93d663e3038593797b35e1c3718cf9f31cfc662915c205084a8fe6ef79c`
- PLG-03.json: `4557a131465925894ae03296d17f98cf33d0395a5a76fd94722e9e1c8e599a94`

## 1. CAL-02 — принять

Исправление адресует реальную последовательность вычислений: `loss.py:22–74` сначала вычисляет нормированный residual/square, а поздний reducer не гарантирует безопасный reverse-mode AD. Proposal требует исключить evaluation-only operands **до** nonlinear operations. Это не разрешение скрывать NaN/Inf в исходном prediction: отдельный исходный model-output guard сохраняется независимо от маски.

Три случая не смешаны: ненулевой train support; полностью замаскированный target при другом поддержанном target (нулевые contribution/gradient/Hessian); полностью пустой corpus (нет fit до optimizer). Held-out finite float32 value `3e38` при fixed scale10 даёт square порядка `9e74`: переполнение именно float32, а не абстрактное «large float». Изменение такого held-out значения должно оставлять train loss/gradient/Hessian/реальный Optax step неизменными. Evaluation metric при этом вправе сообщить range limitation.

Полностью проверен и прежний конкретный TEST04, не только новый текст маски. Actual income-tax mechanism оставляет reported income1 и меняет government balance от −.5 на `r`; θ=`r−.5`. Два target residual — θ−1 и θ−9. Веса `[9,1]` / `[1,9]` дают weighted loss90/730, constant constraint penalty6, totals96/736, physical gradients−36/−164, Hessian20. При bounded `r=sigmoid(u)`, u=0: gradients−9/−41, Hessian1.25. Numeric-domain epsilon=1e−8; float32 `1+ε` округляется в1, поэтому oracle не пропускает скрытый scale factor. Центральная разность с h=1/8 дала20. Сопоставлены `calibrator.py` target/constraint/Hessian closures, `bijectors.py` и actual fiscal mechanism. Ни fake simulator, ни mocked Hessian для этих чисел не нужен.

Общий AD принцип подтверждает [официальный JAX FAQ](https://docs.jax.dev/en/latest/faq.html#gradients-contain-nan-where-using-where): маска результата после небезопасной ветви не эквивалентна безопасному operand внутри неё. Native JAX0.8.2 eager/JIT/Optax всё ещё должен проверить реализацию; документация сама по себе PASS не даёт.

## 2. BKT-02 — принять

Правильно разделены **валидность строки/residual**, представимость производной суммы и authority итоговой оценки. `evaluator.py:72–225` и свежий validator `ir/analytics/backtest.py:368–585` действительно формируют квадраты/суммы; изменение только producer без readback оставило бы несовместимость. Proposal явно распространяет versioned range semantics на свежего читателя и сохраняет legacy handling.

Для residuals `[0,1e308]` независимый Decimal1200 oracle и scaled L2 дают MAE `5e307`, RMSE `7.071067811865476e307`: оба конечны, SSE непредставима. Для `[1e154,1e154]` каждый квадрат представим, сумма уже нет, RMSE остаётся `1e154`. Для пары `1e308` даже absolute-error sum непредставима, но MAE/RMSE равны `1e308`. Таким образом row count нельзя уменьшать из-за overflow промежуточного aggregate. Scaled norm вычисляется как `scale*sqrt(sum((r/scale)^2)/n)`, safe mean — отдельно.

Сохранены subtraction-overflow как настоящий invalid residual, denominator/accounting, неодинаковые размеры групп при micro-pooling, macro distinction, interval comparability и withholding unsupported trust. `null + explicit reason/version` для суммы не подменяется нулём и не делает свежего читателя доверчивее. Нового универсального статистического framework здесь не требуется.

## 3. UQS-01 — принять

Выбран общий FED-owned finite-binary64 helper; UQS остаётся потребителем, а не вторым владельцем численной арифметики. По [CPython3.14 source](https://raw.githubusercontent.com/python/cpython/v3.14.0/Lib/statistics.py) `statistics.mean` делит exact-ratio total до финального преобразования; `fmean` использует floating `fsum` и не является допустимой незаметной заменой. Это соответствует locked Python profile, без новой зависимости.

Проверены cancellation, одинаковые большие значения, обычный `[1,3]`, subnormal `[1e308,−1e308,3*ulp(0)]`. Fraction-from-float и Decimal-from-float1200 сошлись; последний mean равен минимальному subnormal `5e−324`. Перестановки и повторение **всего** multiset сохраняют среднее. Не требуется незаконное unweighted mean-of-unequal-group-means; дублирование не превращается в независимые наблюдения или более узкую uncertainty.

Независимость названа честно: Fraction oracle имеет общую арифметическую основу с реализацией `statistics.mean`; дополнительный Decimal crosscheck и конкретные аналитические значения полезны, но не объявляются доказательством всего пространства binary64. Bounds/carrier semantics и source identity не расширены численным исправлением.

## 4. PLG-03 — принять после поправки

Scalar policy fixture привязан к actual continuous ActorCritic, а не к случайной координате скрытой сети. При всех weights/biases0, logstd0, scalar actor-output bias μ непосредственно задаёт Normal mean. Для raw advantages `[+1,−1]` популяционные mean0/std1 и float32 `K=fl32(1+fl32(1e−8))=1` соответствуют `rl.py:139–143`.

Три ratio пары различают оба знака advantage и две стороны clipping. Независимый расчёт с **stored float32 old_log_probs** дал losses −.2, .100000012232, .299999985781; gradients по μ 0, −1.000000005085, −.999999998880. Предъявленные fixed rtol5e−6/atol2e−6 достаточны относительно ожидаемого rounding, но не разрешено расширять их после факта. Removed clip и reversed policy sign действительно различаются. GAE returns/advantages `[2.25,2.5]/[2,2]`, `[2,2]/[1.75,1.5]`, `[1,2]/[.75,1.5]` совпали с reverse recurrence actual owner. Terminal unit не отменяет native intermediate-terminal refusal.

Добавленные component cases закрывают описанный выше gap. Fixed old policy/advantages/returns — unit targets, не обход on-policy data contract: actual action-law consistency остаётся TEST01; original collector→executor→GAE→PPO→Optax, action effect, artifact/fresh readback обязательны отдельно. Ненулевой градиент не объявляется улучшением welfare или convergence.

Inactive-padding control корректно обозначен **проверяемой гипотезой**, не подтверждённым runtime bug. Same shape, active indices, seeds/keys и initial actor/optimizer исключают ложную RNG-invariance претензию при изменении размера массива. Меняется только разрешённый inactive payload finite→NaN; stored data не переписывается, active NaN отвергается. Если существующая граница уже защищает вычисления, обязательной лишней sanitization patch нет. Источник опасения — unmasked temporal features/actor forward и поздние masks, но runtime outcome здесь не измерялся.

## 5. DOE-02/03 — принять как bounded qualification

Проверен действительный locked sklearn1.8.0: для dense600×100, cap5 auto выбирает randomized, не covariance_eigh/full. [Source dispatch и truncated fit](https://raw.githubusercontent.com/scikit-learn/scikit-learn/1.8.0/sklearn/decomposition/_pca.py) подтверждают существование explicit solver/oversamples/iterations/normalizer/random_state parameters. [`check_random_state(None)`](https://raw.githubusercontent.com/scikit-learn/scikit-learn/1.8.0/sklearn/utils/validation.py) использует global legacy state; integer создаёт отдельный. Поэтому локальный derived PCA-stage seed и actual resolved solver record необходимы сверх одного sampler seed. Proposal не навязывает full SVD любому production размеру и не обещает bitwise replay между разными backends/версиями.

**Малые analytic fixtures корректны.** Для приведённой 3×5 матрицы первые четыре centered столбца имеют один общий score и loading v=(1,2,3,4), пятый ортогонален им. Nonzero squared singular values60 и2/3, ratios90/91 и1/91; feature projector `diag(vvᵀ/30,1)`. Для `[I5;0]` centered Gram `I−11ᵀ/6`, eigenvalues1 (кратность4) и1/6; cap1 объясняет6/25=.24. При повторном собственном значении сравнивать конкретную rank1 axis/projector нельзя — proposal этого не требует.

**DCT — прямой matrix oracle, а не притворный policy model.** Для600×100 `Dij=2^(−j/4)*sqrt(2/600)*cos(π(i+.5)j/600)` столбцы центрированы/ортогональны, singular values известны независимо от tested PCA. Stdlib проверка выбранных столбцов1–6,100 дала максимальную orthogonality error2.20e−15; первые пять variance ratios .2928932188, .2071067812, .1464466094, .1035533906, .0732233047. Optimal rank5 residual=.6532814824. Frobenius projector identity `sqrt(10−2||QᵀU5||²)` корректна для двух rank5 orthonormal bases, не зависит от знаков и не требует600×600 allocation. Actual randomized approximation и допуски должны проверяться native; аналитическая структура не равна выполнению sklearn.

**Legendre/Morris — отдельный параметрический end-to-end witness.** `M_ab(x)=2^(−(10a+b)/8) P_a(2x1−1)P_b(2x2−1)` зависит только от двух входных параметров; повторённая точка обязана давать тот же output. Используется independent three-term recurrence, не row index либо trajectory identity. [SALib1.5.2 source](https://raw.githubusercontent.com/SALib/SALib/v1.5.2/src/SALib/sample/morris/morris.py) согласуется с200 ungrouped trajectories×3rows и num_levels8. Восьмиточечная сетка по каждой оси допускает64 точки, centered rank≤63, поэтому rank>15 математически возможен; при levels4 rank≤15 был бы невозможен. Proposal правильно не требует полного rank100.

Кандидаты seeds `[13,17,19,23]`, критерии rank>15 и `(s5−s6)/s1≥1e−3`, порядок выбора первых двух и freeze объявлены **до tested PCA**. Используются actual SALib design и parameter-only model, независимый full-SVD preflight; нельзя подменить output DCT-строками, подогнать tolerances или выбирать по tested result. Если двух seed нет — BLOCKED/NOT_RUN, не фиктивный PASS. В этом review preflight не выполнялся, поэтому существование двух подходящих realized matrices не утверждается.

Практическая заметка, не дефект: output j=0 постоянный. Actual `MultiOutputAnalyzer.analyze` отбрасывает zero-variance columns, поэтому raw600×100 превращается в600×99; центрированный нулевой столбец спектр не меняет, randomized branch остаётся тем же. В execution record следует сохранить обе формы. NumPy full SVD — независимый adapter route, но может разделять LAPACK-основу со sklearn; собственно mathematical independence даёт отдельный DCT oracle. Сохранены failure policy до PCA, original run accounting, imputation/CI limitations, fresh reader, ABBA replay и global-RNG-state control.

## Итоговые границы согласования

- Все шесть corrections улучшают содержательное свидетельство существующей lane capability, а не только структуру QA. Нет обязательной новой библиотеки, параллельного владельца или fixture-specific branch в продукте.
- LANE-03/04/10 deltas не превращают bounded unit oracles в общую empirical authority; старые end-to-end и source-bound readback остаются обязательными.
- Ещё нужны native CAL masks/AD/Optax, BKT/UQS persistence, PLG eager/JIT/real update/inactive pair, DOE finite-seed preflight/PCA/Morris/replay. Их результаты **NOT_RUN**, не «почти PASS».
- Permissions blockers отсутствуют. Менялись только собственные review/artithmetic artifacts. Авторская адресная PLG поправка повторно проверена; proposal самим reviewer не редактировался.
