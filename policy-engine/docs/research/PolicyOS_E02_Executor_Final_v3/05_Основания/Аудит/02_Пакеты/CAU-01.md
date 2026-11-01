# CAU-01 — standard DiD: дизайн, covariance, confidence level и metadata
## C52 · 1 ноября 2026 года

**Порядок:** 52/127, LANE-05. **Исходные IDs:** B204, B205, B206, LA-016 (этап 1/2). **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит. Свежая проверка после внешнего сохранения C51; утраченный прежний C52 не используется.

## Решение

Содержательный ремонт исходных проблем есть: standard DiD отказывает при отсутствии pre-period, actual cluster route считает CR0 вместо переименованного HC1, confidence level меняет границы в обоих callers, metadata отделены от deprecated wrapper. Known ATT=3 и old-slot standard equivalence сохранены.

**Остался C52-R01:** уникальный `NaN` в unit identity проходит admission и считается кластером, но equality mask не включает его наблюдения в covariance score. На finite control ATT=3,125 не меняется, report остаётся `SUCCESS` с четырьмя clusters, а SE становится **0,5077524002897 вместо 0,5659615711336**. Это не общий отказ от unit-cluster реализации: корректные string/int labels и её полезная invariance работают.

**12 bounded MATCH, 16 неизменённых existing test bodies PASS изолированно.** MATCH P09 означает воспроизведение дефекта. Exact AST численных owners и реальные Pydantic input/report validators исполнены; native package/registry/CAS и statsmodels reference — BLOCKED/UNRUN. Полного statistical или migration закрытия нет.

## 1. Матрица исходных ID

| ID | Исходная проблема | Текущее подтверждение | Остаток |
|---|---|---|---|
| B204 | t0=0 давал неоценимый DiD contrast, insufficient pre-trend считался passed | Общий panel сохраняет t0=0; standard method возвращает INPUT_INVALID без point; known ATT=3 сохранён; not_testable/nonrejection/violation разделены без identifying authority | G01 native; G02 реальные предпосылки |
| B205 | cov_type только переименовывал HC1; repeated periods снижали SE как новая информация | Реальные HC1 и unit-cluster CR0 различаются; независимые finite algebra controls совпадают; unit permutation и 2x/10x техническое повторение сохраняют CR0-SE | **R01 NaN label теряет score**; G01/G02 |
| B206 | 80/99% меняли label, но не boundaries в DiD/RDD | Оба actual callers используют critical value из уровня; положительный SE даёт возрастающие widths; invalid levels отвергаются | G01 native; G02 coverage; RBC отдельно CAU-03 |
| LA-016 | Dedicated methods зависели от deprecated metadata | Module constants и отдельные copies; actual MethodMetadata ownership; mutation old metadata не меняет dedicated report; old slots дают равный standard effective request | G03: staggered у CAU-02, registration/replay closure у CAU-05 |

Полная карточка, строки 6324–6487, прочитана, включая protected LK05. Общая `PanelObservationalData` не ужесточалась механически, `did.py` и реальные causal packages не удалялись. No installs, source edits, commits или services.

## 2. Producer → typed report → ограниченный consumer

Current owner `_run_standard_did` проверяет pre-period и оба treatment regimes **до** расчёта. Dense panel DTO уже проверяет binary treatment, finite numeric outcome, размеры, post-period и отказ repeated cross-section. Затем caller выбирает реальный covariance helper и возвращает `CausalEffectReport` с effective procedure, `n_clusters` и confidence metadata. [S01:322–475](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L322-L475) [S02:45–144](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/protocols.py#L45-L144)

`_wrap_did_output` связывает actual report с `report/result` и envelope с `envelope/uncertainty_envelope`. Diagnostic contract содержит recomputed input/result hashes. В P11 actual extracted report DTO прошёл JSON roundtrip с diagnostics/method_params. Его настоящий `to_uncertainty_envelope` body передал **gate_eligible=False** и на success, и source-read failure route. Сам envelope constructor здесь fixture, CAS/dematerialization не исполнены. [S01:97–105](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L97-L105) [S01:478–523](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L478-L523) [S05:541–705](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal.py#L541-L705)

Следовательно, `SUCCESS` здесь — численная оценка, **не подтверждённое causal identification**. Нельзя объявлять ошибочный SE уже опубликованной policy authority; такого пути C52 не исполнял. Но отсутствие authority не делает потерю score допустимой для numerical candidate.

## 3. Дизайн и inference: что действительно сохранено

**P03/P04/P08:** panel t0=0 успешно конструируется, standard method возвращает точный `standard DiD requires at least one pre-treatment period`. Корректный fixture восстанавливает ATT≈3. Нечисловой outcome, repeated cross-section и отсутствие control не проходят соответствующие реальные boundaries. При 1–2 pre-periods diagnostic — `not_testable`, `passed=False`; отсутствие обнаруженного тренда — `no_detected_pretrend`, а deterministic differential trend — `evidence_of_violation`. Во всех трёх случаях identifying authority отсутствует. [S01:268–320](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L268-L320)

**P02/P05:** для четырёх units независимый расчёт идёт не через owner design matrix, а через четыре cell means и unit-level pre/post changes. ATT=3,125; HC1-SE≈0,9042722672588; CR0-SE≈0,5659615711336. Для CR0 складываются squared deviations unit changes внутри treated/control, делённые на квадраты числа units в каждой группе. Это конечное algebraic identity для данного balanced design, **не statsmodels execution** и не coverage study. Unit permutation и техническое повторение каждого периода 2 и 10 раз сохраняют cluster-SE. [S01:197–265](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L197-L265)

**P12 removal control:** принудительная замена cluster helper на existing HC1 только в isolated namespace возвращает 0,90427 под label cluster; independent unit-change oracle обнаруживает несоответствие. Это различающая проверка, а не assertion одного имени в metadata.

CR0 прямо назван uncorrected, inference scope — `large_independent_units`; `finite_cluster_guarantee=False`, `parallel_trends_identified=False`. Поэтому четыре units в fixture не представлены как достаточная асимптотическая выборка. HC1 имеет scope `iid_rows`, не универсальное обещание пригодности для любого panel dependence. [S01:444–472](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L444-L472)

## 4. C52-R01 — неполное разбиение observations на clusters

**Приоритет высокий, уверенность высокая в ограниченном воспроизведении.** Panel проверяет только shape unit_ids. Cluster boundary требует число уникальных labels, равное числу units. Для `[NaN, 1, 2, 3]` это четыре. Далее `np.unique` перечисляет NaN, но `cluster_ids == NaN` ложно для всех rows, поэтому соответствующий score равен нулю. Report сохраняет `n_clusters=4`. [S02:128–134](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/protocols.py#L128-L134) [S01:223–265](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L223-L265)

**P09:** четыре observations первого unit не принадлежат ни одной mask. Actual typed report имеет status SUCCESS, прежний ATT и заниженный SE. Independent reference после явного удаления только первого unit score даёт ровно наблюдаемые 0,5077524002897. Explicit per-unit `cluster_var=[NaN,1,2,3]` воспроизводит то же поведение при обычных исходных unit_ids.

Минимальное направление: у текущего canonical unit-cluster owner определить допустимость labels и проверять partition completeness — каждое observation должно иметь ровно один group membership. Missing/non-reflexive identity должна получить точный отказ или обоснованную normalization; простое увеличение/decrease count не чинит потерянный score. Не заменять normal-label CR0 на HC1, не запрещать строковые identities и не добавлять новый estimator subsystem.

Показаны только эти finite inputs. Присутствие NaN identities в реальном production dataset, частота/масштаб последствий и downstream policy publication не установлены.

## 5. B206: actual level в обоих callers, не только report label

**P06:** уровни 80/95/99% дают DiD widths ≈2,317743 / 3,544682 / 4,658502; conventional RDD widths ≈0,081021 / 0,123911 / 0,162847. Point и SE при смене уровня сохраняются, critical values сверены с `NormalDist`. 95% использует прежний нормальный z(.975). Invalid levels, включая NaN/infinity, отвергаются; неизвестные covariance/cluster names не получают silent HC1 fallback. [S01:59–65](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L59-L65) [S04:36–42](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/rdd.py#L36-L42) [S04:453–645](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/rdd.py#L453-L645)

Исполнен conventional sharp RDD, не RBC. Правильный quantile не исправляет covariance, bandwidth, bias или scientific assumptions автоматически; CAU-03 остаётся отдельным последующим пакетом.

## 6. LA-016: сохранить useful separation, не объявлять migration закрытой

`_DID_ASSUMPTIONS/_DID_EQUATIONS/_DID_CITATIONS` принадлежат module owner. Legacy и dedicated classes получают отдельные mapping copies; actual MethodMetadata дополнительно сохраняет независимые immutable mappings. Замена legacy metadata не меняет dedicated assumptions или actual standard report. Old outcome_panel/treatment_indicator adapter приводит к тому же effective request и равному report/warnings. [S01:43–56](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L43-L56) [S01:1014–1190](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L1014-L1190) [S07:817–950](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/base.py#L817-L950)

Class decorators/signature registration в probe пропущены. Staggered effective request принадлежит CAU-02, прекращение generic planning route и historical FQN replay — accountable CAU-05. Этот этап не является разрешением удалить старый adapter или весь файл.

## 7. Открытые квалификационные границы

- **C52-G01:** native supported Python/dependencies, registry/dispatcher/output slots/CAS/fresh consumer и independent statsmodels suites. Pytest/statsmodels отсутствуют; ordinary did import остановлен на Python 3.14 syntax `uncertainty.py:287` под Python 3.12. Эти ограничения не являются product R.
- **C52-G02:** реальные identifying assumptions и пригодность large-unit normal inference/finite-cluster coverage. Existing limitations и candidate status нужно сохранить. Synthetic known ATT не делает предложенную LLM causal structure эмпирически подтверждённой.
- **C52-G03:** оставшийся LA migration window квалифицируется последующими designated owners, без второй независимой реализации common inference.

Полные focused tests прочитаны; 16 bodies выполнены с minimal approx/monkeypatch. Единственный statsmodels body — UNRUN, не заменён fake library. Начальный harness range-error сохранён; исправлен только внешний script, final exit 0. [Диагностика](../04_Проверки/C52_CAU01/bounded_diagnostics.json) · [Команды](../04_Проверки/C52_CAU01/commands.json) · [Границы](../04_Проверки/C52_CAU01/native_verification.json) · [Источники](../05_Источники/C52_источники.json) · [Остатки](../01_Реестры/C52_остатки.json).

**52/127 пакетов рассмотрены ограниченно; 125 уникальных B/LA частично оценены. Следующий — CAU-02. Полного закрытия нет.**
