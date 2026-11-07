# BKT-03 — остаток, статистический тест и честный downstream
## C34 · 31 октября 2026 года

**Исходные IDs:** B172, B173. **Порядок:** 34/127. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Аудит без изменения продукта.

## Решение

**Исходные repairs присутствуют:** постоянный ненулевой residual сохраняет descriptive magnitude/sign и отдельную непригодность t-test; отсутствие SciPy не вызывает normal approximation под чужим именем. Настоящий SciPy result передаёт method/backend/version/statistic/p; fresh reader перепроверяет его, а actual packet-section снимает stale p, сохраняя полезное описание.

**24 MATCH, 0 ERROR** в окончательном bounded execution. Найден локальный **C34-R01**: producer `np.mean` и строгий reader `math.fsum/n` расходятся при cancellation конечных residuals; весь report отклоняется, хотя сценарные ошибки пригодны. Native CAS/C5b/полный packet и repository tests не запускались; pytest отсутствует.

## 1. Матрица исходных задач

| ID | Проверенный ремонт | Остаток |
|---|---|---|
| B172 | Constant10 сохраняет magnitude10; signed residual не становится optimistic/pessimistic без ориентации; n<3/variance limit отдельно; exact zero — отдельный контроль | C34-R01: cancellation producer/reader; C34-G02: единицы, направление, независимость и scope |
| B173 | Настоящий SciPy t-test либо explicit unavailable; method identity сохраняется; fresh reader проверяет p/version/bias projection | C34-G01: native CAS→C5b→packet; C34-G02: научные предпосылки |

[Полная карточка](../05_Источники/BKT-03_исходные_строки.txt), строки4221–4308. Не следует восстанавливать прежнее значимое normal approximation ради старого поведения или требовать одинаковой положительной квалификации при отсутствии backend.

## 2. Описательный остаток не зависит от доступности p

P01: `[10,10,10]` даёт MAE10, descriptive bias magnitude10, residual_signpositive, direction_statusnot_established, overallUNKNOWN; pNone, reasonzero_variance, trust отсутствует. P02 отрицательный сдвиг сохраняет знак и magnitude10, но не получает оценочное название. P05 n2 сохраняет magnitude1 с `insufficient_observations`. [S01:1542–1660](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L1542-L1660)

P03/P04 точный ноль при n3/n1 — `exact_zero`, без method/p claims, отдельный point-fit контроль. Это не доказательство независимых повторов или полноценной predictive calibration. P11 `[-1,0,1]` имеет mean0, но ненулевой MAE и настоящий p1; diagnostic остаётся available/not_established, trust не появляется. P12 `[-1,3,3]` различает magnitude5/3 и MAE7/3. Сохраняется именно абсолютный **signed mean**, не произвольно заменённый MAE.

## 3. Backend действительно выполняет названный метод

P06 `[0.5,1.5,2.5]`: actual wrapper и отдельный вызов настоящего `scipy.stats.ttest_1samp` совпали, p≈0.121690. Сохранены statistic, backend version и method ID. Это маленький вычислительный reference, не coverage campaign. [S01:1663–1726](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L1663-L1726)

P07 controlled import denial сохраняет три comparison rows, MAE1.5 и magnitude1.5, но даёт explicit unavailable с точной причиной; ни p, ни test identity не выдуманы. P08 отсутствие метода, P09 invalid p, P10 invalid statistic также не превращаются в available. Эти отрицательные ветви используют явно заданные fault fixtures; положительный backend настоящий.

Actual DTO требует полную identity для available и запрещает её для неисполненного теста. Nominal method name и source rows недостаточны без результата; потому report не называет иной расчёт t-test. [S02:153–204](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/backtest.py#L153-L204)

## 4. Producer → JSON readback → fresh verifier → packet section

P13 сохраняет actual report в обычный JSON файл, читает actual BacktestReport и заново исполняет fresh verifier. Сохраняются method/backend/version, p, n, signed mean, holdout window и выбранные train/validation/holdout roles. Это **не owned CAS roundtrip**. Source reconciliation проверяет complete metric set, actual residual rows, scope, count/mean и statistic. [S02:583–736](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/backtest.py#L583-L736)

P14 подменяет только p на старое normal-like0.009375; P15 backend_version; P16 p в descriptive bias card. Actual fresh verifier снимает статистические поля, оставляя validated mean1.5 и magnitude1.5. P17 backend исчезает после записи — тот же conservative residual-only output. P18 forged exact_zero и P19 чужой scope отвергнуты уже actual IR. [S03:172–322](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/governance/backtest_matrix.py#L172-L322)

P23/P24 исполняют **полную настоящую `_build_backtest_section`**. В P23 она публикует computed diagnostic p≈0.121690 и trustNone. В P24 stale p превращается в unavailable, pNone, но mean1.5 остаётся. Контекст, reference DTO и selected-report loader здесь контролируемые fixtures; загружается уже проверенный actual report. Поэтому не заявлены native manifest binding, полный BuildDecisionPacketNode или nested C5b delivery. [S04:255–350](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/decide/decision_packet/outcome_sections.py#L255-L350)

Полный найденный regression test actual CAS→C5b→packet с p/version/bias forgery, исчезнувшим backend, source-row mismatch, legacy marker и forged-zero прочитан. Он поддерживает существующий owner design, но **не исполнен** в этой среде. [S09:4066–4622](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/nodes/test_decision_packet_node_v3.py#L4066-L4622)

## 5. C34-R01 — cancellation ломает согласование двух правильных ролей

P21: finite residuals `[1e16,1,-1e16]`. Actual evaluator успешно сохраняет три конечные rows и finite error statistics. Producer `_detect_systematic_biases` использует NumPy mean0 и не создаёт ненулевую bias card. Actual IR использует `math.fsum(values)/n = 1/3` и отклоняет весь report: `metric diagnostic does not reconcile source count/mean`.

P22 переставляет **тот же multiset** в `[1e16,-1e16,1]`; producer mean становится1/3, report проходит. Это не square overflow C33: squares здесь конечны, проблема — нестабильное суммирование signed residuals и несогласованная producer/consumer policy. [S01:1555–1561](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L1555-L1561) [S01:1637–1660](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L1637-L1660) [S02:591–606](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/backtest.py#L591-L606) [S03:250–254](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/governance/backtest_matrix.py#L250-L254)

Строгий reader полезен: он **не допускает ложный neutral report**. Его нельзя ослабить ради прохождения примера. Остаток — согласовать устойчивую signed-mean reduction у existing producer/reader и добавить cancellation/permutation regression. Если конкретный statistical backend не поддерживает диапазон, следует сохранить полезные finite scenario metrics с explicit diagnostic limitation, а не терять весь результат. Production prevalence и реальный admission bypass не доказаны.

## 6. Содержательные и исполнительные границы

**C34-G02:** residual independence, effective n, multiplicity, population scope и metric orientation явно остаются assumptions в DTO. Вычисленный p не доказывает их. P20 для `[-1e-14,0,1e-14]` показывает absolute std floor1e-12: statusnot_computable/reasonzero_variance, хотя математическая sample std1e-14 ненулевая. Это текущая numerical policy, а не доказательство нулевой дисперсии; перед научной интерпретацией нужно определить допустимые единицы/масштаб. Nonzero diagnostic при этом не стёрт и не превращён в trust.

**C34-G01:** native pytest attempt для полного найденного test_bkt_03.py остановлен до collection: pytest отсутствует. Ни repository test, ни native CAS/C5b/full packet не объявлены выполненными. Первый и второй probes имели по22 MATCH/2 harness ERROR — сначала отсутствовал module export, затем final return line350 не вошла в extraction. После исправления только harness выполнен свежий полный24/0; все логи сохранены.

Сохранить descriptive rows, conservative direction, настоящую SciPy identity, exact-zero control и fresh residual-only degradation. Локально согласовать signed mean; затем выполнить найденную native цепочку в поддерживаемой среде и квалифицировать предметные предпосылки выбранного метода. Новая параллельная архитектура проверки не нужна.

[Диагностика](../04_Проверки/C34_BKT03/bounded_diagnostics.json) · [Команды](../04_Проверки/C34_BKT03/commands.json) · [Native границы](../04_Проверки/C34_BKT03/native_verification.json) · [Источники](../05_Источники/C34_источники.json) · [Остатки](../01_Реестры/C34_остатки.json).

**34/127 пакетов рассмотрены ограниченно; 88 уникальных B/LA частично оценены. Следующий — BKT-04.**
