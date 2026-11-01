# CAU-02 — staggered DiD: единицы наблюдения, фиксированный target и согласованный null test
## C53 · 1 ноября 2026 года

**Порядок:** 53/127, LANE-05. **Исходные IDs:** B207, B208, B209. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит. Свежая проверка после внешнего сохранения C52; утраченные прежние результаты C53 не являются evidence.

## Решение

Исходный bootstrap готовых ATT(g,t) заменён **общим influence каждой panel unit**, включая вклад оценённых cohort shares. Текущий scalar estimand явно назван `theta_sel`; H0 и CI вычисляются одной centered studentized Mammen-процедурой с finite-B plus-one inversion. Not-yet-treated eligibility использует `timing > t + anticipation`, а недоступные baseline/control cells не исчезают из target молча.

**11 bounded MATCH; 18 unchanged test bodies / 37 cases PASS изолированно. Нового подтверждённого R нет.** Существующий independent known-DGP test также исполнен: 160 paired repetitions, 6 null rejections, 154 null coverages, 160 alternative rejections, 154 alternative coverages. Это конечный numerical control, **не общее nominal-coverage обещание**. Native registry/dispatcher/CAS/EvalSafety и real-data identification остаются открытыми.

## 1. Матрица исходных ID

| ID | Исходный дефект | Текущее свидетельство | Остаток |
|---|---|---|---|
| B207 | Повторно выбирались готовые cells; одна cell давала [5,5] независимо от unit variation | Unit influence, общий multiplier для зависимых contributions, independent functional derivative; одна cell имеет SE≈1,118 и ненулевой interval | G01 native chain; G02 sampling/inference applicability |
| B208 | Нецентрированные draws сравнивались с самой оценкой | Centered studentized scalar null; p-value и CI используют те же draws, integer tail threshold и closed effect-scale intervals | G01 native; G02 general coverage |
| B209 | Anticipating cohort считалась untreated, missing cells могли менять область | Baseline g−1−a; controls только never-treated или timing>t+a; explicit no-control/baseline refusal; current target/diagnostic readers различают изменения | G01 native; G03 empirical anticipation/identification |

Полная исходная карточка 6488–6600 прочитана. CAU-01 predecessor учтён: metadata separation и common typed report сохранены, но не подменяют inference repair. Исходники/зависимости не менялись.

## 2. Target — намеренное содержательное изменение, не «эквивалентный перенос»

`_staggered_target_contract` задаёт fixed study horizon, допустимые периоды **каждой** cohort, control rule, anticipation и unit alignment. Point — среднее cell effects внутри каждой cohort, затем среднее по estimated shares ever-treated units. Это явно другой functional, чем старое size-weighted среднее всех cells: unequal follow-up не должен скрыто умножать вес ранней cohort. При этом исходный аудит не объявлял старую weighting scheme универсально ошибочной; текущий выбор следует оценивать как **объявленную смену target**, а не numerical identity. [S01:526–639](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L526-L639)

**P03:** две cohort с 2 и 4 units, 4 и 2 eligible periods дают `theta_sel=41/6≈6,833333`, а старый cell-size average — 5,75. Independent weighted empirical functional perturbation каждого unit mass совпадает с actual influence; максимальное расхождение finite derivative ≈8,21×10⁻¹⁰. Это не сравнение implementation с самим собой: oracle отдельно считает weighted means и cohort-share ratio. [S09:46–124](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_did_selected_participation.py#L46-L124)

Target binding включает реальные outcome/treatment/timing/IDs/time_index и explicit target contract. Изменение eligible periods меняет estimate/binding. `time_treatment` управляет общей pretrend diagnostic window, но не fixed staggered scalar — его изменение обнаруживается отдельным diagnostic binding. Это осмысленное разделение, а не требование включать всё в один hash.

## 3. B207 — один draw на независимую unit, не на cell

`_selected_participation_influence` накапливает contribution каждого treated/control unit ко всем используемым cells. Затем добавляет derivative оценённых cohort shares. Shared controls поэтому не превращаются в независимые copies. SE равен norm общего influence / n. [S01:716–765](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L716-L765)

**P04 removal control:** удаление только cohort-share term из audit array уменьшает SE с ≈1,327185 до ≈0,443402 и нарушает independent derivative oracle. Checkout не менялся. **P05:** recorder делегирует настоящему NumPy RNG и видит draw shapes 128×12, 128×12, 128×12, 15×12 для B=399. Каждая строка draw действует на общий unit score; это не resampling шести cells. [S01:935–952](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L935-L952)

**P06 — исходный one-cell counterexample:** treated changes [2,4,6,8], controls 0 дают ATT=5, SE≈1,118034, CI≈[2,763932;7,236068], p=0,0025 при выбранном seed/B. Полный перебор 256 стратифицированных treated-unit means имеет тот же ненулевой SD, тогда как resampling единственной готовой cell имеет support {5}. Перебор — различающий mechanism control, **не та же inferential law и не nominal coverage доказательство**.

Если influence вырожден, current method сохраняет point, но возвращает `ASSUMPTION_FAILED`, без CI/p, с `degenerate_unit_influence`. Например постоянный эффект 2 не превращается в искусственный interval [2,2]. Полезный point-only результат не удаляется. [S01:909–933](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L909-L933)

## 4. B208 — одна finite-B процедура для CI и H0

При H0: theta_sel=`null_effect` method использует centered multiplier statistic, нормированный исходным scalar SE. Tail считается по тем же closed effect-scale intervals, которые порождают CI; Decimal confidence level задаёт integer minimum accepted tail count, чтобы 1−0,95 binary rounding не меняло decision. Plus-one меняет конечное разрешение, а не подменяет null law. [S01:808–835](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L808-L835) [S01:935–998](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L935-L998)

**P08:** для 80%/99 draws, 95%/399, 99%/999 проверены оба reported endpoint и ближайшие внешние `nextafter` values — 12 controls. На endpoints H0 не отвергается, за границей отвергается; tail count, integer rule, p-value и actual report JSON согласованы. H0 в observed point даёт p=1, не меняя interval. Слишком малое B для запрошенного уровня получает точный INPUT_INVALID, не фиктивную точность.

Существующий native endpoint/CAS body не исполнялся: его проверка actual persistence не заменена JSON roundtrip. Отдельный bounded control назван отдельно.

## 5. B209 — полная anticipation область и явные gaps

Baseline — g−1−a. For not-yet-treated control используется never-treated или `timing > t+a`; при g=t+a unit уже недопустима как чистый control. **P07:** ATT(2,2), a=1, baseline=0 исключает cohort g=3, оставляя never-treated indices [4,5]. Cell effect равен 2; старое timing>t правило на том же synthetic input дало бы −3. Aggregate theta_sel равен 6 — это среднее двух cohort effects, не ошибка из-за отличия от одной cell. [S01:642–694](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L642-L694)

Existing bodies проверяют a=0, valid integer a, invalid/ambiguous values, g=0 рядом с supported cohort, отсутствие baseline и частично отсутствующие controls. В последнем случае full requested target не уменьшается молча: возвращается refusal с конкретным gap. NaN unit identity, в отличие от standard CR0 residual C52-R01, **отвергается** этим route при finite JSON binding. Соседний дефект не распространён на другой owner без доказательства.

## 6. Producer → typed report → actual selected reader

**P09:** old slot adapter со `staggered=True` и dedicated request на одном seeded effective input дают равные actual reports. Регистрация/исторический FQN replay здесь не аттестованы: это accountable CAU-05.

В primary Scientist job сначала сверяются actual persisted report/envelope, затем diagnostic и staggered target проверяются как для materialized data, так и для bound source. Это source-read wiring, не fake native run. [S10:462–558](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py#L462-L558) [S10:584–651](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py#L584-L651)

**P11:** два exact downstream reader bodies реально исполнены с actual extracted panel/report DTO. Они принимают current report и отвергают:
1. изменённую diagnostic window при прежнем scalar target;
2. изменённое unit alignment при прежнем target binding;
3. переписанный diagnostic payload вместе с согласованно пересчитанными producer hashes.

Consumer recomputation здесь действительно различает содержание, а не только marker. Но job runner, source loading, CAS, native envelope validation и EvalSafety admission не исполнялись. Typed numerical success не равен разрешению evaluation или causal policy publication.

## 7. Bounded scientific evidence и открытые G

**P02:** неизменённый existing test исполнил 160 paired repetitions по одному известному DGP: 400 independent units, 6 periods, две cohort и never-treated, within-unit AR coefficient 0,6, неодинаковые cohort effects, B=399. Null scalar равен 0, alternative shift=1,5. Получено 6/160 null rejections, 154/160 null coverage, 160/160 power, 154/160 alternative coverage; существующие binomial bounds с probability 0,995 пройдены. [S09:237–274](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_did_selected_participation.py#L237-L274)

**C53-G02:** этот finite DGP не доказывает uniform coverage, arbitrary cluster sampling, shared cross-unit shocks, simultaneous bands или все внешние DiD implementations. Current method явно ограничен large independent units, pointwise scalar, без finite-cluster guarantee. Требуемую более широкую процедуру следует обосновать для конкретного design, а не объявлять отсутствие universal estimator локальным дефектом.

**C53-G03:** реальные parallel trends и anticipation window не выводятся из synthetic controls или LLM-предложения. Negative/gap/point-only результаты полезны и сохраняются без automatic promotion.

**C53-G01:** supported Python 3.14/native suites, registry/RNG injection, CAS/fresh consumer lifecycle остаются BLOCKED/UNRUN. Pytest отсутствует, ordinary public import останавливается на Python 3.14 exception syntax под 3.12. Внешний probe свежо переисполняет SHA-bound C52 setup, но не переиспользует его прошлые результаты. Pydantic validators/report JSON настоящие; registration/signature, metadata-only/unused transport/output/envelope seams перечислены явно.

[Диагностика](../04_Проверки/C53_CAU02/bounded_diagnostics.json) · [DGP](../04_Проверки/C53_CAU02/bounded_DGP.json) · [Команды](../04_Проверки/C53_CAU02/commands.json) · [Границы](../04_Проверки/C53_CAU02/native_verification.json) · [Источники](../05_Источники/C53_источники.json) · [Остатки](../01_Реестры/C53_остатки.json).

**53/127 пакетов рассмотрены ограниченно; 128 уникальных B/LA частично оценены. Следующий — CAU-03. Полного закрытия нет.**
