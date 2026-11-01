# BKT-02 — знаменатели, номинальный coverage и micro/macro
## C33 · 31 октября 2026 года

**Исходные IDs:** B167, B168, B171. **Порядок:** 33/127. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит.

## Решение

**Три исходных ремонта существенно присутствуют и различены исполнением:** missing/invalid ячейки не исчезают из requested; отсутствие CI остаётся unknown; interval availability отделена от hit-rate; nominal/type проходят actual DTO JSON roundtrip. Micro RMSE/MAE/MAPE объединяют достаточные статистики, а equal-scenario macro назван отдельно.

Полный точный point forecast проходит evaluator→aggregate→JSON→fresh trust verifier и сохраняет A; пустой/wrong-key/частичный результат не получает report trust. Это bounded execution настоящих definitions, **не native CAS/workflow и не научная квалификация synthetic данных**.

Найден **C33-R01**: крайние, но конечные числа переполняют square/accumulation, срывая весь scenario вместо сохранения пригодных ячеек и явного ограничения. Native tests заблокированы отсутствием pytest. **24 MATCH, 0 ERROR** в окончательном probe; полное закрытие не заявлено.

## 1. Матрица исходных задач

| ID | Реальный ремонт | Остаток |
|---|---|---|
| B167 | Requested/compared/missing/invalid с адресами; completeness ограничивает score; aggregate требует непустых полных сравнений | C33-R01: numeric-range failure теряет partial result; C33-G01: native цепочка |
| B168 | `within_ci=None` при отсутствии/непригодности; availability и conditional hit имеют разные знаменатели; nominal/type сохраняются | C33-G01: настоящий admitted interval producer; C33-G02: смысл и научная интерпретация |
| B171 | SSE/n для micro RMSE; отдельный explicit macro; pooled absolute/percentage/hit counts | C33-R01: устойчивость накопления; C33-G02: units и содержательные веса |

[Полная исходная карточка](../05_Источники/BKT-02_исходные_строки.txt), строки4084–4220. LK01/LK29/LK30 сохранены: predictive calibration, parameter calibration, drift monitoring и production admission не взаимозаменяемы.

## 2. Ячейки не исчезают из проверки

Evaluator итерирует именно ожидаемые `y_true` cells. Неверный ключ/короткий прогноз попадает в missing; нечисло/NaN/inf — в invalid; пригодные точки остаются. P01: requested3/compared0/missing3, direct score0/F, report eligibilityFalse. P04: одна пригодная точка сохранена рядом с тремя invalid адресами. [S01:72–111](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/evaluator.py#L72-L111)

TrustScorer ограничивает результат минимальной completeness, а aggregate отдельно требует requested=compared>0, отсутствия missing/invalid и согласованного числа rows. P03: удаление трудной точки `[1,90]` против `[1,100]` не улучшило результат: direct score0.95/A→0.5/C; partial report не eligible. Это проверка конкретного различающего примера, не доказательство глобальной монотонности всякого scoring profile. [S02:81–106](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/trust_scorer.py#L81-L106) [S04:1494–1523](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L1494-L1523)

P10 сохраняет полезный положительный контроль: три точных point predictions дают score1/A после настоящих aggregate, pre-persist guard, actual DTO записи/чтения обычного JSON файла и fresh trust verifier. Отсутствующие интервалы при этом **не объявлены измеренным coverage**: P05 оставляет coverageNone и все within_ciNone. Point-fit score не равен научно доказанной predictive calibration.

## 3. Что измеряет interval coverage

P06: один имеющийся и попавший interval из двух ожидаемых точек даёт availability0.5, hit1.0, missing within_ciNone, nominal0.8 и typepredictive. Completeness ограничивает direct score0.5/C. P07 отличает настоящий miss: два hits из трёх. P08 invalid bounds не превращаются в miss — availability1/3, conditional hit1/1. [S01:116–176](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/evaluator.py#L116-L176)

P09 одинаковые наблюдения/bounds сохраняют фактический hit0.8, но профиль при nominal0.8 даёт score1, при0.95 —0.9211. Nominal не подменяет наблюдённую частоту. P23 actual DTO roundtrip сохраняет0.8, predictive и counts3/3. Aggregate сохраняет per-scenario interval contracts; pooled coverage P13=1/4, не macro mean0.5. [S02:43–60](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/trust_scorer.py#L43-L60) [S04:1448–1474](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L1448-L1474)

Нет основания смешивать CI среднего эффекта и predictive interval по историческим outcomes. Текущий typed transport имеет поля nominal/type, но его содержательное основание зависит от admitted producer из BKT-01/FRC-02; простой текст `interval_type` не создаёт это основание.

## 4. Micro и macro действительно разные

P11 для residuals `[0,10,10]`:

| Разбиение | Micro RMSE | Equal-scenario macro RMSE | Micro MAE |
|---|---:|---:|---:|
| Один сценарий | 8.1649658093 | 8.1649658093 | 6.6666666667 |
| `[0]` и `[10,10]` | 8.1649658093 | 5.0 | 6.6666666667 |

Политика записана как `micro_rmse_with_explicit_equal_scenario_macro`. P12 четыре разбиения шести тех же residuals сохраняют RMSE≈2.380476, MAE2, MAPE20 и n6. Общий WeightedScorer не объявлен ошибкой; его reweighting полезен, а обязательная полнота относится к конкретному backtest consumer. [S03:33–75](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/evaluation/scoring.py#L33-L75) [S04:1378–1460](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L1378-L1460)

**C33-G02:** pooling разных величин/единиц и юрисдикций требует заранее определённой сопоставимости и весов. Текущая арифметическая корректность не задаёт её автоматически. Сохранить macro, если сценарии имеют содержательную устойчивую идентичность; не стандартизировать задним числом после просмотра результата.

## 5. Persisted rows проверяются downstream

Actual BacktestReport сверяет counts, residuals, relative errors, bounds/hits, sufficient statistics и overall summaries. P14/P15/P24 отказывают подмене overallRMSE, нарисованному hit без bounds и неверному denominator. Legacy report в P16 остаётся читаемым с полезными rows, но его несвязанный trust снят. [S05:368–578](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/backtest.py#L368-L578) [S05:738–779](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/backtest.py#L738-L779)

Fresh verifier перепроверяет diagnostic result, exact-zero source metrics, scorer profile и marker. P17 чужой compute hash отвергнут; P18 candidate diagnostic не получает trust; P22 настоящая SciPy diagnostics для ненулевых residuals сохраняется, но trust не устанавливается при неизвестном направлении метрики. В данном probe implementation name честно `audit_bkt02.TrustScorer`; это isolated definition, не native module identity. [S06:172–363](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/governance/backtest_matrix.py#L172-L363)

Actual matrix, calibration readout и decision-packet section вызывают этот verifier. Packet не просто переписывает stored trust_score; читает selected report ref и публикует recomputed score либо explicit unavailable. Эти внешние consumers **прочитаны, не исполнены**. [S06:544–592](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/governance/backtest_matrix.py#L544-L592) [S07:663–716](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/governance/calibration_validation.py#L663-L716) [S08:255–349](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/decide/decision_packet/outcome_sections.py#L255-L349)

## 6. C33-R01 — конечный вход не гарантирует вычислимый квадрат

В evaluator `abs_err**2` стоит до проверки finite. P19: `[1,1e308]` против `[1,0]` сначала имеет пригодную точку, затем вызывает **OverflowError**, и scenario не возвращается. Защитный invalid-cell branch не достигается. P20: два residuals1e154 имеют по отдельности конечные squares1e308, но их сумма/mean переполняется; строгий DTO отклоняет non-finite RMSE. P21 residuals1e150 корректно дают RMSE1e150. [S01:99–105](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/evaluator.py#L99-L105) [S01:161–163](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/evaluator.py#L161-L163) [S01:202–205](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/evaluator.py#L202-L205)

Это bounded extreme-range defect, не утверждение о распространённости таких production данных и не false-positive trust bypass: DTO не пропускает inf. Минимальный остаток — явная numerical-range policy существующего evaluator/aggregation owner: устойчивый scaled norm/accumulation там, где поддерживается, иначе typed limitation/учёт непредставимых ячеек без потери пригодных. Нельзя исправлять заменой0/inf или отключением reconciliation.

## 7. Проверки, ограничения и продолжение

Полностью прочитаны найденные `test_bkt_02.py` и mirror-contract `test_backtest.py`. Native attempt остановился до collection: `No module named pytest`; ни один repository test не объявлен выполненным.

**C33-G01:** часть persisted-envelope tests всё ещё подставляет `lambda _state` и один artifacts_index. Текущий caller передаёт store/foundry и требует actual workflow/physical request, selected simulation и admitted propagation. Это source-visible несовместимость fixture с текущим контрактом, **не наблюдённый pytest failure**. Нужно привести test fixture к существующему owner, а не восстанавливать прежний raw-envelope bypass ради старого expected score. [S09:331–495](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_bkt_02.py#L331-L495) [S04:733–834](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L733-L834)

Окончательные24 observations исполняют неизменённые definitions с настоящими NumPy/SciPy/Pydantic. Первый probe имел19 MATCH/5 ERROR из-за пропущенного harness decorator; после включения source line105 выполнен полный повтор24/0. Логи обоих запусков сохранены. CAS/полный package import/workflow, native test suite, научная независимость/репрезентативность и production admission не проверены.

Сохранить все численные ремонты и свежую проверку persisted rows; затем локально устранить numerical-range loss, актуализировать fixtures и квалифицировать один настоящий producer→CAS→reader interval path. Новые глобальные реестры или deterministic model inventor не требуются.

[Диагностика](../04_Проверки/C33_BKT02/bounded_diagnostics.json) · [Команды](../04_Проверки/C33_BKT02/commands.json) · [Native границы](../04_Проверки/C33_BKT02/native_verification.json) · [Источники](../05_Источники/C33_источники.json) · [Остатки](../01_Реестры/C33_остатки.json).

**33/127 пакетов рассмотрены ограниченно; 86 уникальных B/LA частично оценены. Следующий — BKT-03.**
