# STR-01 — direction и occurrence counts до top-k

**C119 · LANE-10 · B106, B107 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

Actual stress loop использует одну typed badness-конвенцию: maximize utility ищет меньшие raw values, minimize cost — большие. Threshold, worst-case, adaptive best и stopping согласованы. Счётчики наблюдённых нарушений вычисляются до dedupe/top-k; ограниченный список больше не задаёт размер нарушения.

**6 MATCH; 3 unchanged test bodies / 8 cases PASS. C119-R01 (low):** unavailable occurrence остаётся одновременно в `valid_evaluation_count`. При этом score всё ещё `None`, is_robust=false — ложного допуска не установлено. Protected finite score намеренно held/unbound без independent selected-objective intent; это не следует «исправлять» снятием guard.

## 2. Матрица исходных оснований

| ID | Исходный ремонт | Actual capability | Остаток |
|---|---|---|---|
| B106 | Не вычислять score/counts из короткой presentation list. | Top-k1/10 меняет только examples; 10 одинаковых occurrences дают high_count10 и unique_count1. Source reader считает passed/total по complete occurrence rows, не dedupe. | R01: unavailable входит в valid metadata. G01: protected adversarial score остаётся unbound; численный positive path не исполнялся. |
| B107 | Одна семантика worst/threshold/search для обоих направлений. | Utility10/−5 выбирает−5; cost−5/10 выбирает10. Adaptive history хранит raw8/−4 и правильно обновляет best; invalid typed direction отказан до sampling. | Native CompositeObjective/StrategyAdapter/CAS consumer — G02; compatibility-only helpers не объявлены actual owner. |

## 3. Producer → consumer

[Direction intake и badness comparison](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/adversarial.py#L489-L563) фиксируют typed direction до работы и проверяют finite evaluator result. [Badness/threshold owner](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/stress_report.py#L135-L184) переиспользуется detector и stopping, без второго optimizer.

[Actual adaptive loop](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/adversarial.py#L820-L982) больше не подаёт универсально negated value. Наличие compatibility class NegatedCompositeObjective не означает, что она владеет текущим поиском. Legacy duck-composite adaptation остаётся отдельной совместимостью, не selected-intent authority.

[Report projection](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/adversarial.py#L984-L1040) сохраняет observed/unique/presented units отдельно. [Fresh resolver](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/doe/stress_report.py#L1010-L1124) требует complete ordered rows и не выдаёт finite fraction при skipped/invalid/zero denominator. Однако adversarial source evidence несёт rule само в себе: независимая selection reference не приходит, поэтому reader намеренно возвращает unbound. Этот reader прочитан, не выполнен.

## 4. Проверки

| Проверка | Результат |
|---|---|
| P01 | 2 unchanged top-k/lower-tail bodies и 6 direction cases PASS. |
| P02 | MAXIMIZE: worst−5; MINIMIZE: worst10; по одному нарушению, score=None. |
| P03 | 10 повторных fixture occurrences: high_count10, observed10, unique1, presented1. |
| P04 | Actual SEARCH_LOOP после32 real SciPy initial rows: ещё2 attempts, raw history8/−4, правильный worst−5/10 и stopping. Custom generator, не StrategyAdapter. |
| P05 | Typed unavailable: attempted1, unavailable1, invalid0, но valid1. Invalid-mapping control: valid0/invalid1. Оба non-authoritative. |
| P06 | Actual finite denominator helper совпадает с capped generator; explicit empty fixture не выглядит robust. |

[Probe](../04_Проверки/C119_STR01/probe_str01.py) · [unavailable result](../04_Проверки/C119_STR01/run03/unavailable_result.json) · [diagnostics](../04_Проверки/C119_STR01/bounded_diagnostics.json) · [команды и все попытки](../04_Проверки/C119_STR01/commands.json).

## 5. Остаток и сохраняемое поведение

**C119-R01 — диагностический счётчик (low).** Ветка unavailable увеличивает отдельный счётчик и добавляет skipped outcome, но report metadata считает valid как `total_evaluated − invalid_evaluation_count`. Поэтому неизвестный objective ошибочно попадает также в valid. Согласовать единицы attempted/valid/unavailable/invalid; сохранить точные причины и conservative score refusal. В P05 set_adequacy_status=unverified, robustness_score=None, is_robust=false. Никакого false acceptance или потери всех evidence не доказано.

**C119-G01 — selected intent.** Current reader честно отказывается квалифицировать rule, выбранный самим outcome basis. Нужна привязка существующего request/run-state intent к candidate/plan/source profiles, а не новый registry или producer assertion. Не отменять полезные raw worst-case/violations из-за отсутствия authority; не выдавать их за protected finite score.

**C119-G02 — native chain.** Source-only тесты с реальным CompositeObjective cost, exact CAS profiles, self-claimed available и fresh Level5 прочитаны, но не запускались. Native import блокируется Core 3.14 syntax на Python3.12; pytest отсутствует. В runner ArtifactRef annotation неактивно Any и hash — fixture, поэтому CAS identity не аттестована. No production model, prevalence или scientific coverage claim.

[Исходная карточка](../05_Источники/STR-01_исходные_строки.txt) · [pinned sources](../05_Источники/C119_источники.json) · [остатки](../01_Реестры/C119_остатки.json) · [границы](../04_Проверки/C119_STR01/Чтение_и_границы.md).

**119/127. LANE-10 рассмотрен последовательно и ограниченно; это не implemented/accepted lane. Следующий BER-01. Осталось8 пакетов, фаза заданий исполнителю ещё не начата.**
