# LANE-02 — Search, optimisation, funnel и transfer

**16 исполнительских пакетов; все новые TEST — NOT_RUN.** Основание `20d9009be21097bfbdc38a546a15cc60213b8ace`. 127/127 — полнота phase1 аудита, не выполненные ремонты. [Общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## Точный порядок реестра

| Пакет | Исходные IDs | Практическая задача |
|---|---|---|
| [CTL-01](../02_Пакеты/CTL-01.md) | B118, B119, LA-015 | Поздний ответ не попадает в другое исследование; уже полученная работа остаётся доступной после ошибки/отмены, а пустые предложения завершаются без выдуманного научного исчерпания. |
| [CTL-03](../02_Пакеты/CTL-03.md) | B120, B121, B123 | Sentinel расходует ресурс, но не загрязняет обучение; новые оценки не теряют квоту из-за warm history, а invalid typed result не становится лучшим по удобному scalar. |
| [SRV-01](../02_Пакеты/SRV-01.md) | LA-014 | Один ответ принимается ровно один раз, цель запроса не теряется, а lightweight contracts и законные исторические адреса продолжают работать. |
| [SRV-03](../02_Пакеты/SRV-03.md) | LA-015 | Обычный кандидат и контрольный sentinel реально проходят codec/benchmark/reader, partial run переживает сбой; LA-015 принимается по реальному consumer, не новому имени класса. |
| [CTL-02](../02_Пакеты/CTL-02.md) | B124, B125, B126 | Сохранённое исследование продолжается тем же RNG/Sobol потоком; невалидный restore не портит живой state, а предметные даты не исчезают из идентичности. |
| [STP-01](../02_Пакеты/STP-01.md) | B41, B122 | Исследование не останавливается по отвергнутому embedding или переполнению; настоящая эвристическая стабильность и ресурсный stop остаются полезными и явно ограниченными. |
| [OPT-01](../02_Пакеты/OPT-01.md) | B108, B109, B110, B111 | Получить из настоящих измерений согласованный фронт и перечитать его без потери split/unit/direction; не объявлять частичный набор полным пространством политик. |
| [OPT-02](../02_Пакеты/OPT-02.md) | B112, B113, B127 | Настоящий SearchSpace ведёт от proposal к выполненному MethodJob и source-admitted history; конечное пространство не тратит работу на скрытые дубли. |
| [OPT-03](../02_Пакеты/OPT-03.md) | B114, B115 | Совместимые оплаченные наблюдения действительно достигают GP; append сохраняет learned basis, а отклонённый snapshot не уничтожает действующий поиск. |
| [OPT-04](../02_Пакеты/OPT-04.md) | B116, B117 | Реальная оценка правильного кандидата улучшает champion на одной явной comparison basis; развитие цели разрешено через честный переход. |
| [FUN-01](../02_Пакеты/FUN-01.md) | B156, B158, B159 | После разрешённого изменения основания продолжить нужную работу, не переплачивая за уже пригодный immutable source и не переиспользуя старый допуск. |
| [FUN-02](../02_Пакеты/FUN-02.md) | B157, B160, B162, B165 | Получать полезный reduced/full результат без aliasing и ложной bootstrap certainty; empty/partial/zero остаются различимыми у настоящего consumer. |
| [FUN-03](../02_Пакеты/FUN-03.md) | B161, B163, B164 | Поздняя реальная оценка уточняет своё знание, калибровка не выдумывает измерения, а нормальный разрешённый promotion действительно проходит protected writer. |
| [TRN-01](../02_Пакеты/TRN-01.md) | B128, B130, B131, B132 | Сохранённые пригодные наблюдения доходят до target training либо честной переоценки, не меняя время, feasibility и происхождение. |
| [TRN-02](../02_Пакеты/TRN-02.md) | B129, B133, B134 | Найти доступный совместимый опыт, прочитать exact snapshot и пережить ошибку native индекса без смешения vectors/metadata. |
| [TRN-03](../02_Пакеты/TRN-03.md) | B135, B136, B137 | Полезный lesson переносится по явным фильтрам, не омолаживается чтением и одинаково объясняется в search и report после restart. |

Companion JSON: **68 REQ / 68 TEST**, 80 audit residual records, 95 remaining obligations и 101 preservation bindings. Каждый exact inventory ID имеет substantive REQ/test disposition; наличие записи не доказывает исполнения.

## Практический результат и порядок

Реальный поиск выполняет полезные разные действия, сохраняет partial work и воспроизводимое состояние, использует допустимую историю и позволяет осмысленное продолжение. Метрика, proposal, candidate, source admission, uncertainty и полномочие записи остаются разными контрактами.

1. **CTL-01/03 + SRV-01/03:** один lifecycle owner; run affinity, pending→applying→completed atomic tell, empty/sentinel/attempt/cost accounting. SRV-01 — атомарный tell; CTL-01 — failure finalization; SRV-03 — actual SearchLoopRunner/persistence/resume и accountable LA-015 closure. CTL-01 phase1 не закрывает LA-015 целиком.
2. **CTL-02 + STP-01:** общий atomic RNG/Sobol restore и meaningful next consumer; rejection не оставляет будущий embedding; plateau/cosine имеют устойчивый численный контракт. Heuristic/resource stop не scientific convergence. OPT-03 владеет GP staging поверх общего CTL-02 state, не вторым RNG codec.
3. **OPT-01→02→03/04:** immutable complete coordinate/source measurement; actual params/effective action и typed fallback; genuinely conditioned GP и source verifier; comparison-profile-bound champion и cross-process publication. OPT-01 не переписывает уже исправленный skyline. New suite/goal допускается через reevaluation/explicit transition.
4. **FUN-01→02→03:** fresh gates отдельно от source numerical reuse и linked successor; reduced/full config и правдивый interval origin; same-basis current assessment, calibration snapshot и positive protected promotion bridge. Общие funnel/blueprint файлы — последовательный writer. Whole-ticket cache не возвращается ради stale tests.
5. **TRN-01/02/03:** exact historical DTO/time/boolean и numerical admission; bounded compatible discovery/exact refs/atomic native generation; subject context/filters/evidence clocks. Similarity даёт идею, не source receipt. Новая допустимая задача может переоценить идею без переноса старых чисел.

Actual source owner/caller census обязателен перед alias retirement/новым helper; sourceplan test filenames могут быть предложенными. Existing native witnesses используют actual algorithms/serializers/consumer; внешний транспорт можно контролировать, owner под приёмкой не заменяется успехоподобным stub.

## Общие сценарии и single ownership

Определения и инфраструктура: [интеграция LANE-02](../03_Интеграция/LANE-02.md).

| Сценарий | Совместная проверка |
|---|---|
| E02-I02-A | Actual SearchService/MethodJob/runner, fresh state, empty/sentinel, concurrent/delayed tell, cancel→partial persistence; STP current observation. |
| E02-I02-B | RNG/Sobol→effective params→real evaluation→GP/Pareto→champion. Foreign schema, immutable policy, subnormal/overflow, cold/batch exhaustion и competing publish negatives. |
| E02-I02-C | Full vs bound A/B: одинаковые допустимые source computations/costs, fresh gates, full config, actual score zero, interval method, current knowledge и authorized promotion. |
| E02-I02-D | Real saved compatible history→fresh target consumer; ANN final quota, portable NPZ source, old/new snapshots, restart age, no false independent replicas. |

**Разные writer contracts:** OPT-04 owns autotune champion pointer/comparison; FUN-03 owns funnel→existing `run_promotion_with_evidence`/protected runtime writer bridge. Это не автоматически один институциональный акт. DUR-02 lease fence не заменяет purpose-bound policy permit. FUN-03 normal path должен реально commit ровно один раз, а revoke-before-commit — ноль; bool callback не authority. CYC-05 readiness issuer также не подменяет promotion permit.

**Численные controls:** OPT-01 fast strict dominance сверяется с малым independent oracle; >2D bbox proxy не exact HV. OPT-03 использует existing NumPy Cholesky posterior witness на declared native GP profile. FUN-02 ratio имеет equal extreme/max и minimum-subnormal controls с expected0.5, без underflow от `0.5*width`. FUN-03 aligned5/inverse5 ranks дают +1/−1, short/constant — unavailable, не измеренный0. Допуски соответствуют конкретному алгоритму/profile, не глобальной константе.

## Ограниченные решения и полезная способность

DEC-OPT-01-01 определяет actual fiscal stock/flow law; DEC-OPT-03-01 — verifier replay genuinely conditioned source; DEC-FUN-03-01 — concrete method/source numerical assessment; DEC-FUN-03-02 — actual appointed issuer/writer и missing predicates. До выбора зависимый test BLOCKED/NOT_RUN, а остальные known repairs/candidate work продолжаются. Нельзя закрыть capability лишь сохранённым bridge_missing или test plan.

Native hnswlib/GP/MethodJob jobs выполнять только в supported locked runtime и coordinated slot. Стартовая ресурсная политика: максимум два light jobs; один native/numerical без других test jobs. Стоимость измерять отдельно от correctness: bytes budget не RSS limit, requested draws не executed draws, MATCH audit fixtures не project PASS.

## Review-v2: точные metric, exhaustion и reuse границы

- **PS-F01/PS-F07, FUN-03-02/03:** existing tracker rates FP/(TP+FP), TP/(TP+FP), FN/(FN+TN) — FDR, precision, FOR. DEC-FUN-03-03 выбирает operational purpose/metric/tolerance/sampling и migration всех consumers; FNR не навязывается вместо намеренного FOR. Descriptive observed0 при n>0 не квалифицирует population acceptance. Burn-in rejected-label route существует, но cohort/selection/label availability требуют явного contract; audit work входит в общий budget. Explicit predicted/actual score0 сохраняется через None-selection, source/domain guards не расширяются.
- **PS-F03, OPT-02-01:** pending+completed effective identity в declared measurement scope; bounded unsuccessful proposal search сообщает proposal_search_budget_exhausted, а finite_domain_exhausted требует complete bounded census. Genuine independent replica полезна и не запрещена; cosmetic ID/optimizer seed не новая measurement provenance.
- **PS-F02, только optional DEC-OPT-03-02:** strategy-neutral reuse actual measured observations — отдельная capability specification, не mandatory replacement fitted-native guard/local repair DoD. Source prediction/model continuation и measurement validity различны. До отдельной квалификации существующий fitted-native profile и candidate-only reevaluation полностью сохраняются.

I02-A/B/C/D квалифицируют actual producer→persisted state→fresh consumer, независимые objective/GP/Pareto/metric oracles и real costs. Для более широкого free-grow claim нужен frozen materially different compatible holdout, без case-specific code или tuning по holdout. Общие03/aggregate04 изменяет coordinator отдельно; все product tests остаются NOT_RUN.

## Design и приёмка

[System Vision §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): producer→persisted artifact→bridge→actual consumer. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): shadow/candidate работа не автоматическая authority. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): unknown ограничивает затронутый claim, а не всё исследование.

Для приёмки: exact base/patch и writes, existing test selectors проверенные в checkout, actual command/exit/skip, positive+различающий negative/removal control, независимый numerical oracle где нужен, сохранённые refs/readback, protected owner и compatibility/migration остатки. Один shared run переиспользуется только при одинаковой relevant source/backend binding, не считается несколькими независимыми подтверждениями. Новый совместимый ресурс должен работать через общий механизм; действительно недостающая семантика допускает новый общий код, не case-ID branch и не абсолютный no-new-code запрет.
