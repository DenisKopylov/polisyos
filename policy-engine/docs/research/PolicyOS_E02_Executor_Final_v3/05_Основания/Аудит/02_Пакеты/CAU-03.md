# CAU-03 — RDD: реальная ограниченная RBC и linear-memory WLS
## C54 · 1 ноября 2026 года

**Порядок:** 54/127, LANE-05. **Исходные IDs:** B210, B211. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит. Свежая проверка после внешнего сохранения C53; утраченный прежний C54 не используется.

## Решение

B210 уже не сводится к флагу: текущий **ограниченный sharp/fixed-bandwidth RBC** вычисляет и point correction, и variance исправленного estimator. Independent weighted-lstsq sensitivity oracle подтверждает point/SE; удаление отдельно correction или covariance обнаруживается. B211 убрал product N×N diagonal weights и повторный pseudoinverse одной Gram matrix.

**Остался C54-R01:** conventional linear WLS проходит rank guard, но при чистой смене единиц running variable теряет slope в raw Gram pseudoinverse. На том же sharp linear signal с true jump=3 оба runs возвращают `SUCCESS`, однако x,h → 10⁻⁸·(x,h) меняет estimate с ≈3 на **3,14100798995**. Scaled independent WLS и existing normalized RBC control сохраняют 3.

**7 bounded MATCH, 26 unchanged test bodies / 66 cases PASS изолированно.** P06 — воспроизведение дефекта, не product PASS. Existing fixed-design coverage test исполнил 400 repetitions: 371 covered, 400 accepted, 0 failed. Он проходит свой заранее записанный band, но не устанавливает универсальное nominal coverage. Native package/registry/CAS и methodological generalization остаются G.

## 1. Матрица исходных ID

| ID | Исходная проблема | Текущее подтверждение | Остаток |
|---|---|---|---|
| B210 | bias_correction=True менял только metadata; quadratic fit не был RBC | Отдельная ветвь corrected weights с bias derivative и общей HC0 variance, explicit h/b/p/q/profile; independent oracle, curvature, zero-correction, removal и finite heteroskedastic DGP controls | G01 native lifecycle; G02 более широкая inferential/scientific квалификация |
| B211 | N×N diagonal, два pseudoinverse одной Gram matrix | Vector weighting, одна small-Gram pinv; normal-scale point/SE/count сохраняются по 3 kernels × 2 orders и permutation | **R01 raw-scale rank/solve mismatch**; G01 native; G03 measured performance |

Полная карточка 6601–6690 прочитана. Corrected и conventional profiles не смешаны; обычная подгонка не запрещается из-за требований более сильного режима. Source/test/config/dependency edits и установки не выполнялись.

## 2. Actual owner: это не переименованный quadratic fit

`_fit_rbc_polynomial` строит scaled bases x/h и x/b, проверяет support/rank, получает maps для p и q=p+1. Из conventional intercept weights вычитает leading-bias weights. Variance складывает квадраты **combined corrected weights × q-fit residuals**, поэтому bias-estimation uncertainty и её covariance не заменены старым SE. Используется union h/b windows. Это source-declared clean-room профиль, не вызов установленной внешней `rdrobust`. [S01:124–177](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/rdd.py#L124-L177)

Full `pure_step` реально выбирает этот helper при корректном boolean flag. Нужны explicit finite h и b; поддержаны sharp design, q=p+1, HC0, fixed selector, отсутствие requested clustering/masspoint adjustment. Unsupported settings получают typed refusal, а не hidden fallback. Conventional profile остаётся отдельным, с явно названной weighted-residual homoskedastic variance и heuristic bandwidth при default selection. [S01:320–642](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/rdd.py#L320-L642)

**P02/P03:** curved noiseless signal восстанавливает known jump при ненулевой correction; exact piecewise-linear signal имеет нулевую correction. Удаление correction сохраняет RBC markers, но ломает point oracle; удаление corrected variance сохраняет marker, но ломает SE oracle. Следовательно, содержательный результат не сводится к наличию metadata.

## 3. Независимый numerical oracle и конечный DGP

Existing oracle не вызывает owner correction formula: он отдельно делает weighted `lstsq`, затем по единичным outcome perturbations восстанавливает sensitivities исправленного functional и строит HC0 variance. Исполнены h<b и h>b:

- h=0,45, b=0,70: corrected point≈2,050513341916, SE≈0,084945874489; conventional point≈1,952510668425.
- h=0,70, b=0,45: corrected point≈1,990648983130, SE≈0,150922235162; conventional point≈1,824196118084.

Owner совпадает с independent oracle в существующих tolerances. Artificial variance removal даёт ≈0,068886401533 вместо ≈0,084945874489. [S11:55–152](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_rdd_rbc_independent_oracle.py#L55-L152) [S11:225–264](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_rdd_rbc_independent_oracle.py#L225-L264)

**P03 finite coverage:** один fixed design из 400 unique forcing values, piecewise-quadratic mean с true jump=2 и independent heteroskedastic normal noise; 400 repetitions, seed 2026102803. Получено **371/400=0,9275**, внутри existing acceptance [0,915;0,985]. Все 400 fits приняты, failed fits не отфильтрованы. [S11:20–49](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_rdd_rbc_independent_oracle.py#L20-L49) [S11:199–223](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_rdd_rbc_independent_oracle.py#L199-L223)

Это finite profile evidence. Оно не доказывает точное 95% population coverage, arbitrary bandwidth selection, fuzzy/clustered designs, masspoints, произвольные kernels/orders или causal validity фактического dataset. Сопоставление с внешней `rdrobust` не выполнялось; bibliographic label в коде не засчитан как proof theorem.

## 4. B211: полезная экономия действительно действует

Conventional helper вычисляет Xᵀ(w⊙X) и Xᵀ(w⊙y), один `pinv` малой Gram matrix и прежнюю residual covariance. Rank guard остаётся; нет автоматической подмены covariance только ради speed. [S01:69–121](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/rdd.py#L69-L121)

**P01/P02:** existing tests сравнивают point, SE и count по двум сторонам, triangular/epanechnikov/uniform и p=1/2. Независимый tiny diagonal oracle и permutation controls совпадают. В product helper `np.diag` заменён tripwire, small-Gram pinv зарегистрирован один раз. RBC small solves отдельно дают shapes 2×2,3×3 на каждой стороне — не один общий fit, переименованный в correction.

**P05:** direct helper принимает ровно 400 observations одной стороны, делает один 2×2 pinv и не вызывает diagonal allocation. Для float64 weighted design 400×2 — 6400 bytes, для прежней diagonal 400×400 — 1 280 000 bytes. Это **размеры структур**, не измеренный peak RSS или speedup всей системы. Tiny test oracle намеренно может строить diagonal matrix; это не production allocation.

## 5. C54-R01 — rank admission и numerical solve расходятся

**Приоритет высокий, уверенность высокая в bounded reproduction.** Conventional basis использует сырые powers x. Сначала `matrix_rank(weights[:,None] * X)` принимает rank=2. Потом `pinv(XᵀWX)` применяет собственный relative singular-value threshold к Gram matrix с квадратом conditioning. Принятое направление может быть уже отброшено solve. [S01:98–120](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/rdd.py#L98-L120)

**P06:** 400 unique x, одинаковые y=1+0,3·x_original+3·I(x≥0), cutoff=0; explicit h=0,7, затем x,h умножены на 10⁻⁸. Outcomes, assignment, relative weights и число admitted observations не меняются. На scale=1 jump≈3; на scale=10⁻⁸ jump≈3,141008 и SE≈0,005937. Оба actual typed reports имеют `SUCCESS`, rank guard на right side показывает 2. Right Gram singular values после rescaling — ≈69,8492 и 1,88775×10⁻¹⁶; slope не участвует в effective pseudoinverse.

Независимый weighted-lstsq в координате x/h возвращает ≈3 в обоих случаях. Existing RBC с normalized basis также возвращает ≈3. Поэтому это **не невозможный дизайн, не отсутствие опоры и не необходимость RBC для linear signal**, а conventional numerical residual. RBC implementation целиком не объявлена сломанной.

Минимальное направление — согласовать conventional basis/solve/rank: x/h scaling либо weighted QR/SVD, сохранив конкретную covariance formula и support. Добавить unit-rescaling invariance и effective-rank controls к текущему owner. Не лечить problem только metadata rank, не отключать guard и не требовать пользователю включать другой inferential profile для корректного ordinary fit.

Production prevalence, все numerical scales/orders и итоговая policy publication не установлены. Подтверждён конечный silently wrong numerical result при SUCCESS.

## 6. Producer → actual input/report, но не full native custody

**P07:** actual `materialize_input` сохраняет cutoff из typed fallback, подставляет bound vectors и приводит к jump≈2,5. Без cutoff actual Pydantic contract отказывает; threshold не угадывается. Whole method report JSON roundtrip сохраняет corrected estimate, SE, h/b/p/q, variance profile и input digest. [S01:300–318](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/rdd.py#L300-L318) [S02:989–1032](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/protocols.py#L989-L1032)

Actual extracted `CausalEffectReport` validators и JSON используются, а envelope dependency — fixture. Настоящий report projection body передаёт `gate_eligible=False`. Generic input components, registered dispatcher, persisted CAS и fresh native reader **не выполнены**. Source tests этих путей прочитаны, не превращены в PASS через mock store. [S10:125–167](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_rdd_rbc.py#L125-L167) [S13:33–77](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_rdd_dml_input_materialization.py#L33-L77)

## 7. Сохраняемый результат и остаток

- **Сохранить:** отдельные conventional/RBC profiles, реальные corrected point+variance, explicit unsupported limits, vector weights, cutoff-preserving materialization, input-bound numerical profile, useful non-gating candidate output.
- **C54-G01:** supported Python 3.14/native registry/input-output/CAS tests. Pytest отсутствует, ordinary public import блокируется Python 3.14 exception syntax под 3.12. Signature/registration пропущены в AST; два signature tests UNRUN.
- **C54-G02:** более широкая scientific qualification и реальные continuity/manipulation/bandwidth assumptions. Synthetic curvature и finite coverage не превращают LLM-предложенную causal story в empirical authority.
- **C54-G03:** измеренный end-to-end performance, если он нужен для acceptance. O(n²) weight storage устранён на inspected owner, но peak memory/speedup не измерялись.

26 unchanged bodies / 66 cases состоят из 10/23 conventional regressions, 10/30 RBC controls и 6/13 independent oracle/DGP checks. Два native CAS bodies не исполнялись. Setup C52 повторно выполнен с pinned helper SHA; прежние результаты не переаттестованы. Финальный probe exit 0, Git clean, no installs.

[Диагностика](../04_Проверки/C54_CAU03/bounded_diagnostics.json) · [Coverage](../04_Проверки/C54_CAU03/bounded_coverage.json) · [Команды](../04_Проверки/C54_CAU03/commands.json) · [Границы](../04_Проверки/C54_CAU03/native_verification.json) · [Источники](../05_Источники/C54_источники.json) · [Остатки](../01_Реестры/C54_остатки.json).

**54/127 пакетов рассмотрены ограниченно; 130 уникальных B/LA частично оценены. Следующий — CAU-04. Полного закрытия нет.**
