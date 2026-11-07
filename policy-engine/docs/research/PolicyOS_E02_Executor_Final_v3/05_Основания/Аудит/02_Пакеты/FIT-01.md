# FIT-01 — неизменяемый fit-core, текущая диагностика и ресурс folds
## C60 · 1 ноября 2026 года

**Порядок:** 60/127, LANE-05. **Исходные ID:** B54, B56. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Свежая проверка после внешнего сохранения C59.

## Решение

Исходная устаревшая diagnostic policy и общий изменяемый reader **не воспроизвелись**: actual cache хранит fit-core, а hit создаёт отдельное представление с текущим contract. Изменение scientific fit inputs действительно вызывает refit, включая одинаковый caller label. Внутренний fold-пул заменён последовательными folds внутри уже допущенной внешней работы; все repeats/seeds сохраняются.

**6 bounded MATCH; 11 неизменённых test bodies /49 cases PASS изолированно. Подтверждённых R в этом проходе нет.** Проверялся настоящий численный module с sklearn, но не native PolicyOS bootstrap, outer pool/CAS или научная валидность произвольного TMLE результата. G01/G02 остаются открытыми.

## 1. Матрица исходных требований

| ID | Исходный смысл | Фактическое evidence | Остаток |
|---|---|---|---|
| B54 | Дешёвая текущая диагностика без refit; data/seed/split identity; изоляция readers | P01:48→100; P02 actual fit n600 и precomputed n120; P03 все32 поля и7 same-label invalidations; P06 actual payload | G01 native consumer/persistence; G02 scientific qualification |
| B56 | Ограничить допущенную работу, а не число научных повторов; не создать nested deadlock | P01 cap1 synthetic tripwire; P04 actual EIF/ATE/CI equality; P05 два actual fits,12 folds, peak2 total/1 per fit | G01 actual worker queue/failure/CAS; G02 representative resource measurements |

Полная исходная карточка7156–7248 прочитана. Ограничение ресурса — не требование восстановить старый pool любой ценой; важен сохранённый scientific plan и реальное admission.

## 2. B54: fit и текущий reader действительно разделены

`_ATENuisanceFitCore.from_bundle` сохраняет immutable numeric bytes и собственную metadata. `materialize` возвращает fresh bundle, current contract, отдельные scaler/вложенные manifests и обновляет diagnostic split_policy. `_readonly_array` использует immutable bytes backing и отдельный ndarray view: изменение reader shape не изменяет форму следующего hit. Это не просто frozen dataclass marker. [S01:288–351](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py#L288-L351)

**P01:** исходные synthetic regressions подтверждают48→100 и ess_aware→off без нового fit, отсутствие загрязнения следующего reader и обязательный refit при data/seed change. **P02:** stronger actual n600 run выполняет6 real folds один раз, затем current threshold1000 и policy изменяются без дополнительного fold. Для всех четырёх массивов попытка включить writeability отказана; изменение shape и nested selection record не меняет следующий reader. Old contract не переписывается на месте.

Cache identity включает полные X/T/Y hashes и fitting fingerprint даже при explicit label. Offered precomputed bundle сверяется с current identity и разрешается через контролируемый core; его predictions не принимаются за authority. **P02:** подмена offered mu1 на900 игнорируется; changed data/missing identity отказаны. [S01:746–819](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py#L746-L819) [S01:1014–1048](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py#L1014-L1048)

**P03:** actual fitted same-label controls отдельно меняют X,T,Y,seed,folds,model иsplit; каждая требует другой fit identity. Полный контракт содержит **32 поля:17 fit fields и15 current-view fields**. Existing all-axes test реально вызывает models для каждого случая, считает folds: fit changes дают нужный refit; diagnostic/execution/targeting views сохраняют core, но получают current contract. Это полный field denominator данного contract, не выборка по нескольким названиям. [S09:147–185](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_tmle_fit_contract.py#L147-L185) [S09:256–329](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_tmle_fit_contract.py#L256-L329)

## 3. B56: один уровень параллельности вместо вложенного fan-out

Actual owner формирует весь task list по repeats/folds/seeds, затем последовательно выполняет каждый fold. Diagnostics явно сообщают requested flags/cap и effective workers=1, policy=`serial_folds_within_admitted_job`; система не утверждает, что requested parallel был реализован. Причина в коде — outer Scientist job уже держит permit, а transferable nested permit отсутствует. [S01:244–259](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py#L244-L259) [S01:878–980](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py#L878-L980)

**P04:** actual n240 TMLE при serial и requested parallel/maxcap0 даёт побитово одинаковый EIF, одинаковые ATE и CI; все6 folds сохранены. **P05:** два одновременно допущенных внешним audit executor actual fits, каждый n240,3folds×2repeats,seeds31/211. First-fold barrier создаёт реальную overlap opportunity: peak total=**2**, per fit=**1**. Каждый исполняет все шесть(seed,fold) пар, всего12. Propensity,mu1,mu0,trim_mask и split manifests точно совпадают с отдельным serial run.

Это содержательное подтверждение numerical composition, **не actual Scientist pool run и не throughput benchmark**. Внешний ThreadPoolExecutor — явно ограниченная fixture. Измеренная величина — активные fold calls, не число всех BLAS/OS threads. BLAS/OMP выставлены1 для bounded audit job.

## 4. Где настоящий общий ресурс и что ещё не проверено

Соседний `budget_middleware` управляет monetary reservation/settlement, а не fold worker permits. Actual outer owner — LocalWorkerPool: очередь ждёт capacity, active counter увеличивается до worker invocation и освобождается в finally; parent-context route сохраняет receipt contract. [S06:117–206](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/runner/local_pool.py#L117-L206) [S07:29–91](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/runner/worker_pool.py#L29-L91)

Existing native tests уже проверяют budget1/2, очередь четырёх studies, все24folds, parent output/trace и fresh CAS reader. Отдельный failure test проверяет освобождение slot и сохранение waiting sibling. Эти полные tests прочитаны, но **не выполнены**; не нужно придумывать новый scheduler или новый бумажный contract вместо существующего acceptance owner. [S09:377–555](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_tmle_fit_contract.py#L377-L555) [S09:556–747](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_tmle_fit_contract.py#L556-L747)

**C60-G01:** supported runtime требуется для этих native lifecycle/persistence checks. Current pytest отсутствует; ordinary import падает на Python3.14 exception syntax под Python3.12.14. Это ограничение среды, не дефект numerical module. Реальные sklearn1.8.0,NumPy иSciPy доступны; isolated module run их использует.

**C60-G02:** последовательные внутренние folds — допустимая консервативная текущая policy, не универсально оптимальная мощность. При требовании inner parallelism следует расширять существующий admission и измерять throughput/RAM/waiting; не урезать repeats и не создавать cyclic nested pool wait. Отсутствие такого benchmark не доказывает замедление или дефект одиночного fit.

## 5. Producer → current payload → consumer

**P06:** настоящий `fit_tmle_ate` для n360 затем `result_payload` вызываются с cold/current diagnostic contracts. Всего6 real fold calls, fit identity сохраняется; current nuisance diagnostics содержат threshold1000. Result остаётся `candidate`, `gate_eligible=False`, basis=`consumer_asserted`. Исправление cache не создаёт научную authority автоматически. [S01:1233–1386](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py#L1233-L1386) [S01:1423–1466](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py#L1423-L1466)

Source-only `TMLEEstimator.pure_step` передаёт actual X/T/Y и params в этот core, объединяет descriptive result/payload и строит отдельный causal report/envelope. Report проверяет inference profile, limitations, targeting convergence и finite interval; неподдержанный результат остаётся point-free failure report. Native report projection и persisted downstream здесь не исполнены. [S04:378–524](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/treatment_effects.py#L378-L524)

Synthetic DGP служит различающим cache/resource witness, **не empirical policy evidence**. 120-replicate coverage pilot прочитан, не запущен; общий scientific validity, все backend profiles и estimator refit bootstrap не закрыты FIT-01. Универсальная политика может использовать LLM semantic proposer и имеющиеся typed numeric owners, но proposal не заменяет inference admission.

## 6. Что сохранить и оставшаяся работа

Сохранить content-bound fit identity, current reader materialization, immutable bytes/metadata ownership, controlled precomputed resolution, все folds/repeats/seeds и честную effective execution policy. Не добавлять diagnostic threshold в expensive fit key и не выключать полезный cache. Native admission/receipt/CAS checks выполнять существующими tests; resource optimization подтверждать измерениями, а не максимальным worker count.

Два неудачных первых запуска были ошибками внешнего harness: AST locations и неправильное имя payload key. Scripts/logs сохранены; окончательный полный run exit0 после исправления только harness. Исходники/тесты/зависимости repo не изменялись, git status clean, installs/services отсутствуют.

[Диагностика](../04_Проверки/C60_FIT01/bounded_diagnostics.json) · [Команды](../04_Проверки/C60_FIT01/commands.json) · [Native-границы](../04_Проверки/C60_FIT01/native_verification.json) · [Источники](../05_Источники/C60_источники.json) · [Остатки](../01_Реестры/C60_остатки.json).

**60/127 пакетов рассмотрены ограниченно; 140 уникальных B/LA частично оценены. Следующий — STA-01. Полного закрытия нет.**
