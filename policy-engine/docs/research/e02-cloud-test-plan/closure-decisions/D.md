# D — поиск, оптимизатор, перенос истории и funnel

**Исполнение:** читать вместе с [методами](method-decisions.md), [runtime-профилями](runtime-profiles.md), [семантикой](semantic-decisions.md), [контрактами](cross-unit-contracts.md) и [приёмкой](verification-and-closeout.md). Команды и новые test paths ниже — задачи следующей реализации; этот документ их не исполнял. Полный исходный критерий и маршрутизация: [coverage.json](coverage.json), immutable source G97.


## Вердикт для G97

D полностью учтён как исследовательская область: **17/17 пакетов и 45/45 finding IDs** сверены с полными таблицами распределения. Все 45 строк в каноническом `finding-owners.tsv@97c85fa` имеют исходный статус `partial`; в последнем D residual map все 45 строк также `partial`, а `closure_ids` пуст. Ни один вывод этого аудита не повышает статус на `closed`.

Результат D — инженерный кандидат `6ac534aef6d19dc7b6d0cd2f969d16e6d8e756b2` (дерево `69f89374f3c4abc50827ed1d5436c9ed4e050ebf`), описанный агрегированной квитанцией на D topic head `ffbb62165a85a8c8bedd8c11af8246273619ede1`. Текущий интегрированный источник G97 — `97c85fae2d4505ec8248540d98b9556296244208` (дерево `e77c0741d3b19acb43e07a0de2bdb97c8fa98ee3`); точная проверка объектов показала, что все 27 product-source blobs D-кандидата отличаются от G97, а соответствующие G97 blobs все 27 совпадают с D slice-base c40 (`897662caf73bd4487f798d66938b74d7abfe753e`); ни один commit не является предком другого. В G97 есть D `baseline-map-handoff.json`, но нет D `aggregate.json` и нет ни одного из 27 candidate-source blobs. **В точных 27 D mechanism paths G97 всё ещё равен c40; D candidate code не принят, а candidate PASS — evidence D-кандидата, не G integration. Возможный аналог через другие owner paths требует отдельного consumer/property proof; он не заменяет исходник в этой complete 27-path denominator.** `coverage.json` содержит полный список путей и поблочное сравнение.

Исходный критерий и residual row сверены целиком из каждой канонической bundle-страницы и обоих owner TSV: `bundle-owners.tsv@97c85fa` — 127 строк, `finding-owners.tsv@97c85fa` — 282 строки. Baseline D map указывает 17 владельцев пакетов и 45 finding rows. Для исторического среза D: 456 маршрутных строк, 115 исходных source cells, 15 source jobs, 112 source-reported `PASS` и 3 `FAILED`; это компактные отчётные значения, а не повторно прочитанные архивы. Raw archives в D receipt — 0. Поэтому исторический пакетный `PASS` не закрывает критерий и не является свидетельством реально выполненного backend.

Точные источники D, все относительно финального topic head и receipt identity, перечислены ниже; краткие owner freezes обозначают исходник поведения, а не финальный integration target.
- Owner source freeze `search`: `e789e9523725fa081de5cdc69da5938489315b4a` (tree `8baa795f1e191b4bf9c6d6c5dc283bd32bab440f`).
- Owner source freeze `transfer`: `830ddd02dcfbdc6b93492d740b397581b79c82fc` (tree `68ad202bff60a17a15e9500be13d0dcaba28af24`).
- Owner source freeze `lessons`: `66c1a8b17e20fcdf1d36593afb052ff92ed2b171` (tree `a5443d26d3b2e335a4a5eefc5a651e8f3e50e77d`).
- Owner source freeze `funnel`: `63b0eb20a3ed99c72d8b88eea09d80f87ac98495` (tree `392e9d6cae59eb2614619f626f0aaf8b1a001387`).
- Owner source freeze `stress`: `58bccb82f2447fcd8bc3d10ebc89abc69aea71ef` (tree `805f62376d18835cd40e5b47b78f9226d3eba005`).
- Pinned owner handoffs:
  - `baseline` — `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/baseline-map.json@d7705039d1b509fee606d204b60585fcf137dbd8` (SHA-256 `14cee3e4fd1325207e79a0760130d2d1a6f1eeb9e064c9b4d76a3981d7d27c60`).
  - `search` — `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/search-coverage.json@4a390fd4a2f556fd93cd215542e04d4d339cc6ad` (SHA-256 `a2211daf08407a898b92ec57d33ed184242237cdec04944a283f3576d7669ca7`).
  - `transfer_numerical` — `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/transfer-numerical.json@3911345b2fec2c54ae03529bc29b214e79db6aee` (SHA-256 `ef9f277f869e496f8876eca20e99606539bc5be3df310e0554544a8646c01f3c`).
  - `transfer_generation` — `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/transfer-generation.json@3911345b2fec2c54ae03529bc29b214e79db6aee` (SHA-256 `ce8ed67344f06eabde99b8a19e6fda887e1d311088954a1fb060a5ba70e2963e`).
  - `transfer_binding` — `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/transfer-input-binding.json@3911345b2fec2c54ae03529bc29b214e79db6aee` (SHA-256 `2899b883ccb04aef471b5ee82aca958e72e35478d9b91fc76d3d02888237dae7`).
  - `transfer_typed` — `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/transfer-typed-restore.json@3911345b2fec2c54ae03529bc29b214e79db6aee` (SHA-256 `02e70fa12f6eede8117af7dfd43f13d690aba3624284b754be0c90e00ec2b40a`).
  - `transfer_physical` — `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/transfer-physical-types.json@3911345b2fec2c54ae03529bc29b214e79db6aee` (SHA-256 `d001406208a3450f7cde1de9bbffa61e2c5a30ffd4f3f7b81d2ee24a343c7aaf`).
  - `transfer_workflow` — `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/transfer-workflow-4097.json@3911345b2fec2c54ae03529bc29b214e79db6aee` (SHA-256 `eca27e9830231637bf012e1efca796334bb05b977f5c92076bb281e08101bedb`).
  - `lessons` — `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/lessons.json@3e762fbabde70013e50a42e84945066351e71718` (SHA-256 `a1e91657feb3e22681163328f8d441618531f5484c998a08b271edabb345f9c6`).
  - `stress` — `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/stress.json@005a6b1e23dd1ea24d22187ddc22862d24425a99` (SHA-256 `d502bbfd693333a6402f584a205bae55afbe9e59680632eafcf3e0682463567e`).
  - `fun_01` — `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/funnel-01-continuation.json@01e5110f908f5467cfadf67acd595eaf254cbc8d` (SHA-256 `cbb10f3045e8797ba862685e683c79c863b785e7fceb2f5b241b41f20442dba9`).
  - `fun_02` — `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/funnel-02-config-outcomes.json@01e5110f908f5467cfadf67acd595eaf254cbc8d` (SHA-256 `3c733ca7e194524c64a67502e62cba2e3f84d42b41223eee1fabfe49b35e59fe`).
  - `fun_03` — `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/funnel-03-calibration-promotion.json@01e5110f908f5467cfadf67acd595eaf254cbc8d` (SHA-256 `8545c643d589a8a259a00771d005222a9299f054958979cb88d285099557d8ba`).
  - `gp_403_review` — `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/gp-403-fallback-review.json@80cac6b10b42156e18cd73844e7ec279bf05dc96` (SHA-256 `45309b0f8ee3525d02f2f54605ca732194ee39384903c7ea34c82a7afc8b6fca`).
  - `final_contract_review` — `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/final-contract-review.json@7ced8ed4bcf199007aeaa9fda2279aceb975750d` (SHA-256 `56b3b6df805da4875eeec7d2f878cd808437f51f6f014fee876744d00df68b49`).
- Финальные aggregate/residual map: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/aggregate.json@ffbb62165a85a8c8bedd8c11af8246273619ede1` и `.../final-residual-map.json@ffbb62165a85a8c8bedd8c11af8246273619ede1`. Полный D chat result — локальный `thread-D-messages.md` snapshot с указанным ниже SHA-256.

Кандидатные решающие проверки дают полезные, но ограниченные результаты:

- Реальный CPU GP-witness на исходнике `e789e952…` (предок 6ac) исполнил 15 тестов без skip в двух профилях: Torch 2.10 / BoTorch 0.16.1 / GPyTorch 1.15.1 и Torch 2.14.1 / BoTorch 0.18.1 / GPyTorch 1.15.2. Witness проверяет настоящие `train_X/train_Y`, learned parameters/transforms, checkpoint restore, собственный RNG, запрещённый скрытый refit и разрешённый due refit после hard-resource fallback. Это реальный численный путь кандидата, но не production corpus, не двоичная идентичность backend-версий и не authority на происхождение transfer history.
- На 6ac зафиксирован `final-transfer-consumers.log`: 73 PASS по связанным transfer-consumer тестам с реальным CAS/HNSW, WarmStartBridge, SearchLoopRunner, SingleTaskGP training tensors и записью candidate/evaluation artifacts. Контроль удаления content-binding менял actual GP training corpus с 3 до 4 строк при неизменных refs и обнаруживал ровно неверную дополнительную строку. Использованы аналитические fixtures; доказательства production-history или выигрыша оптимизации это не даёт.
- Broad regression выполнен на другом точном target SHA `dabdd83fe235155a91dc6c7b1d85c7cfa5db6346`: 95 whole test files, 879 выполнений, 873 PASS, 6 FAIL, один SALib module skipped. Все шесть selectors отмечены как падавшие и на c40, но доказательства полного знаменателя и нулевого пересечения изменённых входов нет; согласно P41 это **не** inherited-red waiver. Архитектурная проверка на D candidate также FAIL: deep-import diagnostics уменьшились с 157 до 151, удалены 6 D-introduced diagnostic, но общий gate остаётся красным. Ruff source-delta после исправления записан PASS. Ни одна проверка не запускалась мной повторно.
- Статический census `production_invocation` остался `UNRESOLVED` (23 search callables и 3 FUN entries по закреплённым исходникам). Статический поиск не доказывает ни наличие, ни отсутствие served production caller; живой API/deployment execution отдельно не установлен.
- Локальный D chat snapshot `thread-D-messages.md` (SHA-256 `80322e1901b1ab95e94f436e4978b658fb8bb38ccf0774574d97fa4939527ef0`) содержит финальную запись: draft PR #10 и handoff были опубликованы, remote head `ffbb62165` перечитан; автор указывает 15+15 GP PASS, 73 transfer PASS, 873/6/1 skipped broad result, architecture FAIL, все 17/45 учтены и 0 closures. Это согласуется с точными pinned receipts выше; сообщения не заменяют исходные артефакты и их source SHA.

Степень доказательности формулируется буквально: bounded local runtime predicates в candidate receipts — `recomputed` / `independently_reconciled`; original source law, origin, tenant и deployment — `consumer_asserted` или `not_established`; overall `predicate_basis` residual map — `not_established`. Это engineering evidence без institutional authority purpose, без finding closure и без promotion signature. Технические профили B106/B116/B117/B122/B133 выбраны явно: production distribution law, unsupported distributed-filesystem semantics и отсутствующий permission issuer остаются отдельными ограничениями, а не незавершённым выбором локального алгоритма.

## Архитектурное решение и анти-паттерны

Повторное использование имеющихся владельцев — основной выбор: per-run state и существующий SearchLoopRunner; typed objective/frontier; уже имеющийся GP/BoTorch continuation; существующий registry/CAS; HNSW только для обнаружения, CAS для точного содержимого; действующие funnel и lesson consumers. Новый controller framework, отдельный store для переноса, вторая cache identity или вычисление «дешёвого» proxy вместо реального backend не нужны.

Существенные обнаруженные риски — P01/P02 (контракт и candidate artifact могут существовать без workflow bridge), P04/P09 (частичный/no-evaluation/defer/verdict должны переживать переход и projection), P05/P10/P14 (правдоподобная численная строка не даёт право приписать origin/unit/tenant или доказательную силу), P07/P08 (checkpoint identity, semantic dates, RNG stream и evidence clock определяют replay), P29/P32/P33 (маркеры, поля и fixture shape не заменяют запуск настоящего consumer и removal probe), P37/P38 (gate должен перепроверить и саму основу, а не строку `PASS`, имя поля, cost declaration или наличие checkpoint), P35/P36 (выводы считаются только по полному pinned denominator и точным row refs), P40 (вторая ошибка одного класса объединяется в более широкий механизм с одним oracle либо остаётся явно ограниченным residual), P41 (база — точная база D-slice c40). Для каждой строки в `coverage.json` отдельно указаны bounded property, остаток, владелец, candidate oracle и capability-gap label. Этим отчёт не превращает все отсутствующие production inputs в универсальное «ничего нельзя делать»: локальные механизмы уже доказаны там, где есть behavioral witness; не доказана только соответствующая часть цепочки.

### P40 — общие механизмы для более глубоких находок

Связанные same-class механизмы: `B114/B115` — `OPT-03` (saved GP state плюс независимый analytic posterior); `B112/B113/B127` — `OPT-02` (canonical SearchSpace и исполненная action identity); `B129/B133` — `TRN-02` (exact CAS/cache и captured snapshot); `B158/B159` — `FUN-01` (existing persisted charge ledger/resume); `B160/B165` — `FUN-02` (typed outcome и consumer projection). Каждый набор принимает один owner-bundle command/oracle. B164 — исходная owner-permission invariant на уровень глубже: strict bool остаётся self-attested; остановить bool patching и удержать фальсифицируемый `bridge_missing` до typed permit, independent verifier и commit-time revocation. Candidate evidence bounded; G97 acceptance этого falsifier не выполняла. Остальные IDs — distinct classes.

### Смысловые и runtime seams

Указанные ниже `file:line` относятся только к D-кандидату `@6ac534a`; это указатели на проверяемый механизм, а не заявление, что те же строки существуют или приняты в G97.


**Контроллер и checkpoint.** Один экземпляр не должен случайно переносить history, champion, счётчики или изменяемые candidate mappings из прежнего запуска в новый. Выбранный механизм — свежий SearchRunState на каждый run плюс отдельная явная resume-операция; прежний SearchResult — независимый snapshot, который не меняется после выдачи. Пустой batch — не фиктивная научная итерация: различить exhausted, bounded transient pause и repair/error, считать попытки генерации отдельно от evaluation и сохранить реальный partial result. Проверка конечного пространства нужна отдельно от того, что генератор пока ничего не предложил. В candidate это следует читать вместе с `controller.py:588,641`, `run_state.py:36` и native runner/caller из `autotune/runtime.py:185`.

**RNG, время и sampler.** В candidate объектный `timestamp/starts_at` семантического вмешательства остаётся в candidate identity, а transport-created timestamp исключается только по известному typed пути. Python `Random.getstate()/setstate()` захватывают и восстанавливают состояние генератора; persisted codec должен валидировать версию и именно структуру RNG, а не рекурсивно переиначивать metadata и не заменять продолжение повторным seed. Для Sobol достаточно одной идентичности sampler/seed/backend/space и сохранённого логического cursor; продолжение обязано совпасть с uninterrupted sequence. Кандидатная locked-среда зафиксировала SciPy 1.16.3; официальный текущий справочник SciPy v1.18 документирует сбалансированность `random_base2(2^m)`, возможность произвольного `random(n)`, `fast_forward/reset`, RNG и ограничения конечного числа точек; произвольный неполный prefix нельзя называть тем же balanced-design. Это требования воспроизводимости, не требование делать каждый бюджетный запуск размера `2^m`. Candidate loci: `strategies/base.py:103,117,158,210,276`, `strategies/rl_wrapper.py:104,134`, `strategies/space.py:235,253`.

**Pareto и числа.** Выбирать из существующего typed objective/frontier пути. Direction и coordinate identity входят в сравнение; strict Pareto oracle должна видеть точку, доминируемую предыдущими группами; unknown/nonfinite/overflow остаются типизированной unavailable-величиной, не `0` и не winner. Для B108 отсутствующие единицы нельзя «починить» угадываемым alias. B109 математически корректный fast comparator не равен complete global frontier: ему ещё нужен source/run/tenant/cell-bound provider из execution context до served publisher. B111 кандидат не должен допускать unknown persisted schema profile: contract version, который допускает `3.0`, требует положительного known-version и отказного unknown-version пути. В D candidate `ParetoRegistrySnapshot.schema_version` — широкая строка с pattern в `search/pareto_registry.py:89`; JSON-readback идёт через `:240` и `:856`, поэтому тест нужен на неизвестное число, не только на вид строки.

**BoTorch warm-start — не просто сохранённая история.** Настоящий положительный сигнал — совместимые historical observations действительно попали в действительные `train_X/train_Y` GP, выученные параметры и transforms загружены, и posterior/следующая ask совпадают. Контроль только `model_state` bytes или длины training rows недостаточен: при сохранённых маркерах и отключённом `load_state_dict` numerical posterior должен отличаться. В D witness отдельно показано, что пропущенный hidden refit остаётся без вызова fit, но scheduled fit при real hard-resource fallback становится due и исполняется ровно один раз после восстановления ресурса; будущий refit counter и corrupt X/Y/count должны отказать атомарно до мутации модели и RNG. Официальная BoTorch API для `condition_on_observations(X,Y)` описывает продолжение той же модели с новыми точками; `fit_gpytorch_mll()` отдельно оптимизирует GP hyperparameters. Это поддерживает выбранное разделение continuation и scheduled fit, но не отменяет тест именно закреплённой версии/backend/transforms. Candidate loci: `strategies/bayesian.py:345,535,694,713`; восстановление и warm corpus — это разные assertion points.

**Transfer и происхождение.** Embedding/HNSW остаётся retrieval/discovery механизмом; после нахождения run его `ArtifactRef` переносится до загрузчика и содержимое читается точно из CAS. Нельзя делать второй ANN нулевым вектором, чтобы найти blob, который уже адресуем. При возврате transfer rows typed adapter сохраняет исходные evaluation/candidate refs, время и diagnostics; ranking приводит objective direction к одному порядку, но similarity/rank не доказывают допустимость эксперимента. До включения строки в GP надо разрешить ссылку и content-bind candidate, evaluation, source/target bounds, unit, metric/direction, split, run, origin и нужный tenant/evaluator context. Exact ref cache ключуется версией artifact/content; invalid/corrupt/schema-mismatch различаются; ошибочная публикация native index не должна связывать старые векторы с новыми metadata. При чтении уроков query filters проверяются одинаково на local/transfer ветках; evidence creation/producer clock отделён от LRU/last-access, чтобы обычное чтение не восстанавливало доверие. Candidate loci: `agent/vector_memory.py:108,232`, `autotune/warm_start.py:92`, `search/strategies/transfer.py:542`, `search/lessons.py:808,864,952`.

**Funnel/evaluator.** Full и split стадий должны вести к одному effective request и переходу, но declared BudgetState не становится реальным расходом, пока service/caller не подаёт и не закрывает authoritative charge. Результаты различают `evaluated zero`, `empty`, `capped`, `not evaluated`, `partial` и `defer`; uncertainty interval с отсутствующим/невалидным width не превращается в zero; пустой calibration tracker — `not_established`, не normal. Promotion сначала выполняет owner-backed preflight, а непосредственно перед записью перепроверяет candidate, run/ticket generation, policy/time и content-bound evidence. Arbitrary callback, который сам вернул `True`, не создаёт полномочие. Итоговый агрегат DEFER не публикуется как промежуточный APPROVE. Candidate loci: `search/funnel/orchestrator.py:297,899,1099,1124,1141,1241`.

## 17 bundle решений, владельцы и acceptance

Следующий freeze должен быть G97 плюс D-код после явного acceptance/review, а не старый standalone c40-кандидат. Ниже указаны минимальный способ reuse и тесты, которые следует выполнить на принятом integration SHA. Команды — исполняемые в `policy-engine`, тесты существуют на D candidate; в этом research turn я их **не запускал**. Каждому bundle назначена independent oracle помимо candidate receipt.

<a id="bundle-ctl-01"></a>

### CTL-01 — Search run-state: исправление fresh/empty и извлечение владельца состояния

Finding IDs: B118, B119.

Выбранный путь: Сохранить текущий controller/service и разделить конфигурацию и новый `SearchRunState`; завершённый результат отдавать независимым snapshot. Пустой ответ получать как typed exhaustion/transient/repair с отдельным счётчиком proposal attempts.

Альтернатива, которую здесь не выбираем: Do not use `clear()` on a history object already returned to callers; do not call an empty proposal a new scientific iteration or fabricate a candidate.

Проверка корректности/сопровождения: A per-run state prevents cross-run contamination and keeps old outputs immutable; the finite proposal/exhaustion policy is separate from observed no-result counts.

Owner/consumer paths: `policy-engine/src/polisyos/scientist/methods/search/controller.py`, `policy-engine/src/polisyos/scientist/methods/search/run_state.py`, `policy-engine/src/polisyos/scientist/methods/search/service.py`, `policy-engine/src/polisyos/scientist/methods/autotune/runtime.py`.

Эти из перечисленных product paths действительно входят в source-delta 6ac: `policy-engine/src/polisyos/scientist/methods/search/controller.py`, `policy-engine/src/polisyos/scientist/methods/search/run_state.py`, `policy-engine/src/polisyos/scientist/methods/search/service.py`. Остальные — названные upstream/live consumer paths; это не утверждение, что они были изменены.

**Команда на post-integration freeze (не запускалась этим аудитом):**

```sh
cd policy-engine && python -m pytest -q tests/unit/scientist/methods/autotune/test_native_search_lifecycle.py tests/unit/scientist/search/test_search_loop.py tests/unit/scientist/search/test_controller_api.py -ra
```

**Независимый oracle:** Два публичных запуска на разных генераторах: первая history неизменна, вторая имеет свой run state и счётчики; пустое/exhausted/transient предложение ограниченно завершает цикл.

<a id="bundle-ctl-02"></a>

### CTL-02 — Содержательные даты и воспроизводимый RNG/checkpoint

Finding IDs: B124, B125, B126.

Выбранный путь: Переиспользовать state artifact и его явный codec: сохранять semantic dates, RNG codec/version и один Sobol sampler identity+cursor; не использовать seed как псевдо-resume.

Альтернатива, которую здесь не выбираем: Do not recursively strip all datetime-like fields; do not checkpoint only a seed; do not materialize unbounded duplicate prefixes to simulate sampler state.

Проверка корректности/сопровождения: Semantic time remains part of candidate identity; state roundtrip must reproduce the next values. A cursor resumes a prefix but does not imply a power-of-two balanced design.

Owner/consumer paths: `policy-engine/src/polisyos/scientist/methods/search/strategies/base.py`, `policy-engine/src/polisyos/scientist/methods/search/strategies/types.py`, `policy-engine/src/polisyos/scientist/methods/search/strategies/rl_wrapper.py`, `policy-engine/src/polisyos/scientist/methods/search/strategies/space.py`.

Эти из перечисленных product paths действительно входят в source-delta 6ac: `policy-engine/src/polisyos/scientist/methods/search/strategies/base.py`, `policy-engine/src/polisyos/scientist/methods/search/strategies/rl_wrapper.py`, `policy-engine/src/polisyos/scientist/methods/search/strategies/space.py`, `policy-engine/src/polisyos/scientist/methods/search/strategies/types.py`. Остальные — названные upstream/live consumer paths; это не утверждение, что они были изменены.

**Команда на post-integration freeze (не запускалась этим аудитом):**

```sh
cd policy-engine && python -m pytest -q tests/unit/scientist/methods/search/strategies/test_strategy_state.py tests/unit/scientist/methods/search/strategies/test_rl_checkpoint_numerical_oracle.py tests/unit/scientist/methods/search/strategies/test_gp_resume_witness.py -ra
```

**Независимый oracle:** Полный persisted JSON round-trip сравнивает следующий Python RNG draw и Sobol stream с uninterrupted продолжением; независимо сверяет semantic-date identity.

<a id="bundle-ctl-03"></a>

### CTL-03 — Search transition: стоимость, счётчики и typed eligibility

Finding IDs: B120, B121, B123.

Выбранный путь: Один stop/budget owner. Wire existing `BudgetMiddleware` + persisted `BudgetLedger/FileBudgetLedger`; реальный resource owner сообщает измеренную стоимость и стабильный charge-event ID, warm/new/sentinel/evaluation counters остаются отдельными. Для B123 сохранить локальное различие отсутствующего typed входа (разрешён legacy path) и присутствующего malformed результата (не вызывать scalar fallback и не получать `best_candidate`). B123 не делает claim о publication/promotion authority; этот owner-permission boundary отдельно записан в B164.

Альтернатива, которую здесь не выбираем: Не приравнивать iteration counts/trace/estimate к деньгам; не схлопывать warm/new/sentinel; не трактовать malformed-present как отсутствующий typed input и не добавлять authority gate к B123.

Проверка корректности/сопровождения: Ledger oracle сравнивает persisted snapshot до/после реального event, reopen, settled reservation и dedupe. B123 использует существующий `test_malformed_typed_evaluation_cannot_fall_back_to_legacy_objective` в `tests/unit/scientist/search/test_search_loop.py`: malformed present leaves `best_candidate is None` и сохраняет invalid reason; absent typed input остаётся позитивным legacy control.

Owner/consumer paths: `policy-engine/src/polisyos/scientist/methods/search/stopping.py`, `policy-engine/src/polisyos/scientist/methods/search/controller.py`, `policy-engine/src/polisyos/scientist/methods/autotune/bayesian_generator.py`, `policy-engine/src/polisyos/scientist/orchestration/engine/budget.py`, `policy-engine/src/polisyos/scientist/orchestration/engine/budget_ledger.py`, `policy-engine/src/polisyos/scientist/orchestration/engine/budget_middleware.py`, `policy-engine/tests/unit/scientist/search/test_search_loop.py`.

**Команда на post-integration freeze (не запускалась этим аудитом):**

```sh
cd policy-engine && python -m pytest -q tests/unit/scientist/search/test_search_loop.py::TestOptimizationFlow::test_malformed_typed_evaluation_cannot_fall_back_to_legacy_objective tests/unit/scientist/search/test_cost_stopping.py tests/unit/scientist/methods/autotune/test_bayesian_numerical_oracle.py tests/unit/scientist/orchestration/engine/test_budget.py tests/unit/scientist/orchestration/engine/test_budget_middleware.py tests/unit/scientist/orchestration/engine/test_budget_ledger.py -ra
```

`test_budget_ledger.py` — предлагаемое focused coverage, отсутствующее в exact G97 tree.

**Независимый oracle:** Persisted ledger settlement + full/split parity; для B123 — actual SearchLoop consumer, malformed-present не получает scalar fallback и не становится best candidate, а absent typed input продолжает штатный legacy route.

<a id="bundle-fun-01"></a>

### FUN-01 — Версионный ticket и одинаковое full/split продолжение

Finding IDs: B156, B158, B159.

Выбранный путь: Сохранить один `FunnelOrchestrator` transition для full/split и подключить к существующим `BudgetMiddleware` + persisted `BudgetLedger/FileBudgetLedger`. A/runtime resource owner передаёт measured charge event с единицей и стабильным ID; reserve до допуска, settlement/commit либо release после owner outcome, затем snapshot readback. Dedup charge ID расширяет существующий ledger или действует явно bounded at-most-once/reconciliation contract. Trace и `compute_actual_usd` не являются списанием. `RunPolicyBlueprintRuntime` строит orchestrator без supplied `budget_state` — это bridge seam.

Альтернатива, которую здесь не выбираем: Не дублировать stage machine и не считать estimate/trace равным settled resource spend.

Проверка корректности/сопровождения: Выполнить один реальный resource-owner event в full и split. До/после перечитать `FileBudgetLedger.snapshot()` через новый ledger instance и проверить measured spend, remaining, settled reservation, стабильный charge-event ID и одну persisted mutation. Повторная доставка ID не списывает второй раз; snapshots/ticket/effects/stop reasons совпадают. Текущая mutation schema не содержит charge-event ID; расширять этот ledger или определить ограниченный at-most-once writer, не второй subsystem.

Owner/consumer paths: `policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py`, `policy-engine/src/polisyos/scientist/methods/search/funnel/types.py`, `policy-engine/src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py`, `policy-engine/src/polisyos/scientist/orchestration/engine/budget.py`, `policy-engine/src/polisyos/scientist/orchestration/engine/budget_ledger.py`, `policy-engine/src/polisyos/scientist/orchestration/engine/budget_middleware.py`.

**Команда на post-integration freeze (не запускалась этим аудитом):**

```sh
cd policy-engine && python -m pytest -q tests/unit/scientist/search/funnel/test_orchestrator.py tests/unit/scientist/orchestration/engine/test_budget.py tests/unit/scientist/orchestration/engine/test_budget_middleware.py tests/unit/scientist/orchestration/engine/test_budget_ledger.py -ra
```

`test_budget_ledger.py` — предлагаемое focused coverage, которого нет в точном G97 tree.

**Независимый oracle и negative control:** Сохранить traces и `compute_actual_usd=1`, но убрать settlement: snapshot не содержит spend и remaining не снижается. Вернуть механизм и проверить persisted readback, fresh reopen, repeated-ID dedupe и full/split equality.

<a id="bundle-fun-02"></a>

### FUN-02 — Изоляция reduced-config и правдивый результат воронки

Finding IDs: B157, B160, B162, B165.

Выбранный путь: Использовать существующий typed outcome и интервал: настоящий оценённый ноль остаётся нулём, empty/capped/invalid — non-result. Projection проверять у реального consumer.

Альтернатива, которую здесь не выбираем: Do not map empty/error/missing interval to numerical zero or drop `not_evaluated` at output.

Проверка корректности/сопровождения: The typed result preserves the difference between true measured zero and absence; interval arithmetic is finite and width-dependent.

Owner/consumer paths: `policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py`, `policy-engine/src/polisyos/scientist/methods/search/funnel/types.py`.

Эти из перечисленных product paths действительно входят в source-delta 6ac: `policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py`, `policy-engine/src/polisyos/scientist/methods/search/funnel/types.py`. Остальные — названные upstream/live consumer paths; это не утверждение, что они были изменены.

**Команда на post-integration freeze (не запускалась этим аудитом):**

```sh
cd policy-engine && python -m pytest -q tests/unit/scientist/search/funnel/test_orchestrator.py tests/unit/remediation/test_fun_02.py -ra
```

**Независимый oracle:** Независимая арифметика interval и verdict: true zero против empty/capped/failed; отследить реальный consumer projection.

<a id="bundle-fun-03"></a>

### FUN-03 — Текущее знание, calibration routing и pre-commit ограничение

Finding IDs: B161, B163, B164.

Выбранный путь: Сохранить preflight и настоящий write-owner commit guard. Для B164 заменить generic bool/`promotion_write_allowed` на proposed owner-issued typed permit, независимо проверенный как current и привязанный к `candidate_ref`, run/ticket generation, `promotion-write` purpose, policy/schema version, issuer/verifier provenance, valid time и revocation epoch. Write owner проверяет current generation/revocation в той же commit linearization boundary, что и side effect: проверка и эффект сериализованы относительно issuer revocation, а не выполнены как раздельные check-then-write операции. Existing ChampionRegistry сам перечитывает canonical predecessor под своим local lock; caller-supplied expected_predecessor API сегодня не существует, любое расширение обозначить как новую часть среза. Issuer/verifier API пока не назначен: это integrate contract, не существующий PolicyOS permission API; до назначения fail-closed с `bridge_missing`.

Альтернатива, которую здесь не выбираем: Не считать self-attested bool/generic callback разрешением и не превращать локальный stage verdict в publication authority.

Проверка корректности/сопровождения: Recording writer исполняется ровно один раз только с independently verified current permit. Отзыв после preflight, stale generation, absent/fake permit, wrong issuer/candidate/run/ticket/purpose или expiry дают typed denial до side effect. В negative test сохранить `promotion_write_allowed=True`; итоговый aggregate verdict проверять у реального consumer.

Owner/consumer paths: `policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py`, `policy-engine/src/polisyos/scientist/methods/search/funnel/level6_promotion.py`, `policy-engine/src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py`.

**Команда на post-integration freeze (не запускалась этим аудитом):**

```sh
cd policy-engine && python -m pytest -q tests/unit/scientist/search/funnel/test_orchestrator.py tests/unit/scientist/search/funnel/test_level6_promotion.py tests/unit/remediation/test_fun_03.py -ra
```

**Независимый oracle и P40:** B164 — исходная owner-permission invariant на уровень глубже: candidate bool всё ещё self-attests permission. Не открывать новый strict-bool round; удержать фальсифицируемый `bridge_missing` до действующего issuer/verifier и commit-time revocation. При `promotion_write_allowed=True` удалить verifier или отозвать permit между preflight и commit — writer должен остаться на нуле effects; валидный owner-verified permit пишет один раз.

<a id="bundle-opt-01"></a>

### OPT-01 — Метрика, полная координата и строгий Pareto

Finding IDs: `B108`, `B109`, `B110`, `B111`.

Выбранный путь: Оставить typed objective/frontier и строгий Pareto. Добавить run/tenant/cell-bound provider для общего отбора; неизвестные/неfinite величины не превращать в ноль или победителя.

Альтернатива, которую здесь не выбираем: Do not guess units from an alternate key, compare only per-group fronts, or rank unknown/nonfinite values as zero.

Проверка корректности/сопровождения: Typed objective direction/identity supports a complete dominance relation; O(n²) all-pairs is the independent small-fixture oracle, not the production fast path.

Owner/consumer paths: `policy-engine/src/polisyos/scientist/methods/autotune/pareto.py`, `policy-engine/src/polisyos/scientist/methods/search/pareto_registry.py`.

Paths from the D candidate 6ac: `policy-engine/src/polisyos/scientist/methods/autotune/pareto.py`, `policy-engine/src/polisyos/scientist/methods/search/pareto_registry.py`. Остальные owner paths названы как upstream/live consumers, не как изменённые файлы.

**Команда на post-integration freeze (не запускалась этим аудитом):**

```sh
cd policy-engine && python -m pytest -q tests/unit/scientist/methods/autotune/test_pareto.py tests/unit/scientist/methods/autotune/test_pareto_numerical_oracle.py tests/unit/scientist/methods/search/test_hypervolume_limitations.py -ra
```

**Независимый oracle:** Независимая O(n²) all-pairs Pareto oracle над typed ObjectiveValues и exact supported hypervolume oracle.

**Negative controls:** B108: with primary deficit absent, a valid documented alias is used; conflicting or malformed aliases stay unavailable. B109: an earlier candidate that strictly dominates a later-group point must remove it from the combined frontier. B110: equal metric labels with a changed split/unit/direction identity must not compare. B111: unknown/nonfinite/overflow values remain unavailable and cannot rank as zero.
<a id="bundle-opt-02"></a>

### OPT-02 — Настоящий SearchSpace и координаты фактического исполнения

Finding IDs: `B112`, `B113`, `B127`.

Выбранный путь: Использовать один canonical SearchSpace и roundtrip suggestion→execution→result; хранить физические и фактические дискретные координаты, сохраняя distinct proposals.

Альтернатива, которую здесь не выбираем: Do not create a parallel SearchSpace interpretation or use `0` for absent observations.

Проверка корректности/сопровождения: Canonical effective space and execution-coordinate identity make suggest→execute→persist roundtrip meaningful, including discrete projection.

Owner/consumer paths: `policy-engine/src/polisyos/scientist/methods/autotune/bayesian_generator.py`, `policy-engine/src/polisyos/scientist/methods/search/strategies/space.py`, `policy-engine/src/polisyos/scientist/methods/search/strategies/types.py`.

Paths from the D candidate 6ac: `policy-engine/src/polisyos/scientist/methods/autotune/bayesian_generator.py`, `policy-engine/src/polisyos/scientist/methods/search/strategies/space.py`, `policy-engine/src/polisyos/scientist/methods/search/strategies/types.py`. Остальные owner paths названы как upstream/live consumers, не как изменённые файлы.

**Команда на post-integration freeze (не запускалась этим аудитом):**

```sh
cd policy-engine && python -m pytest -q tests/unit/scientist/methods/autotune/test_bayesian_generator.py tests/unit/scientist/methods/autotune/test_bayesian_numerical_oracle.py tests/unit/scientist/methods/search/strategies/test_effective_actions.py -ra
```

**Независимый oracle:** Независимая каноникализация SearchSpace и suggestion→execution→stored observation; physical/effective/discrete action coordinates совпадают.

**Negative controls:** B112: a compatible wrapper exposes the complete canonical SearchSpace protocol and surfaces optional-backend failure distinctly. B113: mutate physical parameters, direction or source observation identity while retaining display labels; persisted history must diverge. B127: two proposals that project to the same discrete executed action are identified/deduplicated after projection while the relaxed proposal and actual effective coordinates remain distinct and recorded.
<a id="bundle-opt-03"></a>

### OPT-03 — Рабочий warm-start и сохранённое GP-состояние

Finding IDs: `B114`, `B115`.

Выбранный путь: Переиспользовать сохранённые X/Y, fitted SingleTaskGP state, likelihood/noise, Normalize/Standardize и RNG. Same-basis resume/append не запускает MLL fit; refit допускается только по versioned due schedule. Расширить существующий test_gp_resume_witness.py независимой fixed-parameter формульной проверкой, не использующей model.posterior в oracle.

Альтернатива, которую здесь не выбираем: Do not rebuild/refit on every resume, accept saved bytes as proof of restored parameters, or forbid a truly due refit.

Проверка корректности/сопровождения: Текущий real BoTorch witness подтверждает backend restore/resume, но не является математическим oracle: обе стороны используют ту же posterior implementation. Формульный код не вызывает model.posterior, берёт fitted state/transforms из persisted model state, сравнивает полную covariance и явно unscale-ит output units.

Owner/consumer paths: `policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py`, `policy-engine/src/polisyos/scientist/methods/search/strategies/_deps.py`, `policy-engine/src/polisyos/scientist/methods/autotune/warm_start.py`.

Paths from the D candidate 6ac: `policy-engine/src/polisyos/scientist/methods/autotune/warm_start.py`, `policy-engine/src/polisyos/scientist/methods/search/strategies/_deps.py`, `policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py`. Остальные owner paths названы как upstream/live consumers, не как изменённые файлы.

**Команда на post-integration freeze (не запускалась этим аудитом):**

```sh
cd policy-engine && python -m pytest -q tests/unit/scientist/methods/search/strategies/test_gp_resume_witness.py tests/unit/scientist/methods/search/strategies/test_gp_resource_resume.py tests/unit/scientist/methods/autotune/test_transfer_workflow.py -ra
```

**Независимый oracle:** На 8–12 distinct non-replicated 1D точках с nonsingular covariance зафиксировать fitted mean/kernel/likelihood noise и transform state. Независимо преобразовать X через сохранённый Normalize и Y в координаты сохранённого Standardize; в double precision считать C=K(X,X)+σ²I, L=chol(C), α=L⁻ᵀL⁻¹(y_std−m(X_norm)), μ_std=m(X*_norm)+K(X_norm,X*_norm)α, V=L⁻¹K(X_norm,X*_norm) и полную latent Σ_std=K(X*_norm,X*_norm)−VᵀV. Перед сравнением unscale prediction: μ=μ_std×s_y+mean_y, Σ=Σ_std×s_y². Сверить mean и full covariance с `SingleTaskGP.posterior(observation_noise=False)` для fitted и restored model. Для append заморозить hyperparameters/transforms и аналитически пересчитать объединённые X/Y без refit; MLL fit count=0 при same-basis resume/append, >0 только при due refit. Если тестируется noisy observation posterior, отдельно добавить шум likelihood на диагональ. Oracle не вызывает `model.posterior`.

**Negative controls:** Keep a valid fitted-state positive control. Then independently omit `state_dict` loading, mutate one captured kernel/noise parameter or transform, or remove an admitted warm row while keeping all marker fields. The analytic mean/full covariance must diverge before publication; same-basis append has zero fit calls and the explicit due-refit control has a fit.
<a id="bundle-opt-04"></a>

### OPT-04 — Привязанный champion и compare-and-publish

Finding IDs: `B116`, `B117`.

Выбранный путь: Использовать один existing ChampionRegistry owner и его local POSIX _promotion_lock/atomic pointer. Каждая promotion задаёт expected predecessor; внутри lock перечитать current, проверить exact candidate/evaluation/suite ArtifactRef content/split/data/metric profile/version basis и затем compare-and-publish. При новой suite переоценить champion на той же базе либо открыть явно отдельное сравнение. Readers видят целиком old/new pointer; claim-adjudication при promotion_basis mismatch fail-closed. Не создавать второй registry/latest pointer или distributed authority.

Альтернатива, которую здесь не выбираем: Do not treat temp-file/rename atomicity alone as compare-and-swap; do not create a second registry owner or claim distributed guarantees outside the existing local registry profile.

Проверка корректности/сопровождения: G97 уже имеет ChampionRegistry._promotion_lock с fcntl.flock, reread/current comparison, atomic temp-file replace и claim promotion-basis digest. Pin one owner. Cross-filesystem/distributed registry guarantees остаются вне профиля, не повод добавлять второй owner.

Owner/consumer paths: `policy-engine/src/polisyos/scientist/methods/autotune/registry.py`, `policy-engine/src/polisyos/scientist/methods/search/pareto_registry.py`.

Paths from the D candidate 6ac: `policy-engine/src/polisyos/scientist/methods/search/pareto_registry.py`. Остальные owner paths названы как upstream/live consumers, не как изменённые файлы.

**Команда на post-integration freeze (не запускалась этим аудитом):**

```sh
cd policy-engine && python -m pytest -q tests/unit/scientist/methods/autotune/test_native_search_lifecycle.py tests/unit/scientist/search/test_frontier.py tests/unit/scientist/methods/autotune/test_registry_and_runner.py -ra
```

**Независимый oracle:** Matched basis проходит; wrong candidate/evaluation/suite ArtifactRef/content/split/profile/version не меняет pointer. Два writer-а с одним expected predecessor: ровно один commit, второй перечитывает/пересравнивает. Reader/reopen получает полный old/new object. Crash injection до/после atomic replace оставляет целый old/new pointer; claim promotion_basis mismatch запрещает publish. Это существующий registry и local POSIX profile.

**Negative controls:** Keep metric field name/value but substitute suite content/split/candidate/profile version; the exact content-bound consumer rejects before pointer change. Remove expected-generation reread/CAS while leaving atomic rename; the competing-writer oracle must fail. Remove promotion-basis digest validation but retain its marker; a mismatched crash-boundary claim must be admitted only in the broken control.
<a id="bundle-srv-01"></a>

### SRV-01 — SearchService: чистые contracts и один ask/tell state transition

Finding IDs: `LA-014`.

Выбранный путь: Оставить SearchService contract чистым от legacy runtime import и side effects; назначить действительного caller/migration owner и переключать одного consumer с characterization trace.

Альтернатива, которую здесь не выбираем: Do not delete the legacy controller in the same step as separating contracts, and do not declare the contract usable merely because it imports.

Проверка корректности/сопровождения: Pure contract import plus one real consumer cutover is a small reversible seam with current owner reuse.

Owner/consumer paths: `policy-engine/src/polisyos/scientist/methods/search/contracts.py`, `policy-engine/src/polisyos/scientist/methods/search/service.py`, `policy-engine/src/polisyos/scientist/methods/search/controller.py`.

Paths from the D candidate 6ac: `policy-engine/src/polisyos/scientist/methods/search/contracts.py`, `policy-engine/src/polisyos/scientist/methods/search/controller.py`, `policy-engine/src/polisyos/scientist/methods/search/service.py`. Остальные owner paths названы как upstream/live consumers, не как изменённые файлы.

**Команда на post-integration freeze (не запускалась этим аудитом):**

```sh
cd policy-engine && python -m pytest -q tests/unit/scientist/methods/autotune/test_native_search_lifecycle.py tests/unit/scientist/search/test_contracts.py tests/unit/scientist/search/test_search_loop.py -ra
```

**Независимый oracle:** Импорт контракта с recording legacy module + реальный service consumer; пути исполнения/transition/result проверяются поведенчески.

**Negative controls:** Import the contract while a recording legacy module is installed and assert no legacy runtime side effect; remove the consumer cutover while keeping contract imports green and the route/result oracle must fail.
<a id="bundle-srv-03"></a>

### SRV-03 — Autotune: native SearchService driver и ограниченный cutover

Finding IDs: LA-015.

Выбранный путь: Переходить существующему `_NativeSearchServiceDriver` по одному live consumer; сохранять историю, stopping, sentinels, partial result, eval failure/resume и возможность ограниченного legacy rollback.

Альтернатива, которую здесь не выбираем: Do not force an all-at-once replacement or erase historical readers before exact trace comparison.

Проверка корректности/сопровождения: One consumer cutover retains stopping, sentinels, partial result and rollback; comparison covers semantic outputs, not iteration count alone.

Owner/consumer paths: `policy-engine/src/polisyos/scientist/methods/search/controller.py`, `policy-engine/src/polisyos/scientist/methods/search/run_state.py`, `policy-engine/src/polisyos/scientist/methods/search/service.py`, `policy-engine/src/polisyos/scientist/methods/autotune/runtime.py`.

Эти из перечисленных product paths действительно входят в source-delta 6ac: `policy-engine/src/polisyos/scientist/methods/search/controller.py`, `policy-engine/src/polisyos/scientist/methods/search/run_state.py`, `policy-engine/src/polisyos/scientist/methods/search/service.py`. Остальные — названные upstream/live consumer paths; это не утверждение, что они были изменены.

**Команда на post-integration freeze (не запускалась этим аудитом):**

```sh
cd policy-engine && python -m pytest -q tests/unit/scientist/methods/autotune/test_native_search_lifecycle.py tests/unit/scientist/methods/autotune/test_registry_and_runner.py -ra
```

**Независимый oracle:** Persist, crash, restart, reopen registry/CAS; равны history/frontier/eval count/failure-resume; отдельно legacy rollback.

<a id="bundle-stp-01"></a>

### STP-01 — Актуальный convergence-сигнал и плато около нуля

Finding IDs: B41, B122.

Выбранный путь: Для B41 сохранить freshness/error admission текущих embeddings. Для B122 выбрать versioned bounded tolerance profile: `abs_tol=0.01` в объявленных единицах objective и `rel_tol=0.01`. Нормализовать направление: gain=`recent_best − historical_best` для maximize и `historical_best − recent_best` для minimize; plateau, когда gain ≤ max(abs_tol, rel_tol×|historical_best|). Около нуля доминирует абсолютная часть. Без objective unit/profile не заявлять plateau/convergence. Это инженерный default, не заявление о statistical significance.

Альтернатива, которую здесь не выбираем: Не делить на near-zero baseline и не подменять objective-scale tolerance машинным epsilon; не выводить freshness из stale vectors.

Проверка корректности/сопровождения: Независимо сверить maximize/minimize, обе стороны near-zero boundary, малый/большой baseline, согласованную unit conversion и отсутствующий unit; stale/model/dimension vectors проверить отдельно. Текущий candidate hardcoded epsilon branch не реализует выбранный профиль.

Owner/consumer paths: `policy-engine/src/polisyos/scientist/methods/search/stopping.py`, `policy-engine/src/polisyos/scientist/methods/search/strategies/base.py`.

**Команда на post-integration freeze (не запускалась этим аудитом):**

```sh
cd policy-engine && python -m pytest -q tests/unit/scientist/orchestration/engine/test_convergence_numerical_oracle.py tests/unit/scientist/methods/search/test_stopping_limitations.py tests/unit/scientist/methods/search/test_stopping_numerical_oracle.py -ra
```

**Независимый oracle:** Direction-normalized gain сравнивается с max(0.01 objective units, 0.01×abs(historical best)); unit conversion вместе с tolerance сохраняет verdict. Без unit plateau недоступен.

<a id="bundle-str-01"></a>

### STR-01 — Направление stress-поиска и независимые от top-k счётчики

Finding IDs: B106, B107.

Выбранный путь: До presentation grouping/dedupe/top-k считать `attempted`, `finite_evaluated`, per-scenario violation occurrence, `unknown/nonfinite` и completeness. При `finite_evaluated > 0` показывать observed empirical robustness `(finite_evaluated - violated_scenarios) / finite_evaluated`; zero denominator даёт unavailable. Unknown или incomplete evaluation маркируются отдельно как partial/conditional. Один scenario учитывается как нарушенный максимум один раз, даже если создаёт несколько issue-групп. Доля описывает finite outcomes в обследованной выборке, не вероятность отказа всего пространства. Full issue payload ограничен k+1.

Альтернатива, которую здесь не выбираем: Не вычислять score из числа unique issues, retained top-k examples или адаптивного экстремума как из популяционной вероятности; не сохранять все большие payloads ради occurrence счётчика.

Проверка корректности/сопровождения: Independent full-stream reference; изменение cap/grouping на том же scenario stream не меняет score/counters. Десять повторов одного issue остаются десятью occurrences; zero/incomplete run не выглядит установленной устойчивостью. Objective direction для B107 проверяется отдельной minimize/maximize oracle.

Owner/consumer paths: `policy-engine/src/polisyos/scientist/methods/search/adversarial.py`.

**Команда на post-integration freeze (не запускалась этим аудитом):**

```sh
cd policy-engine && python -m pytest -q tests/unit/scientist/search/test_adversarial_streaming.py tests/unit/scientist/search/test_adversarial.py tests/unit/scientist/policy_design/test_phase_b_policy_workers.py -ra
```

**Независимый oracle:** Full-history occurrence counter/formula поверх finite outcomes, unknown/completeness отдельно, payload bound ≤k+1. Adaptive/early-stop sample не получает whole-domain probability interpretation без sampling design.

<a id="bundle-trn-01"></a>

### TRN-01 — Численный transfer без фиктивного benchmark

Finding IDs: B128, B130, B131, B132.

Выбранный путь: Переиспользовать warm-start bridge и typed adapter; exact refs и content-bound fields проходят в настоящий GP. Не заявлять production quality/performance без реального исходного evaluator corpus.

Альтернатива, которую здесь не выбираем: Do not substitute embedding similarity/rank for evidence admissibility; do not disable all warm start to avoid identity bugs.

Проверка корректности/сопровождения: Typed adapters preserve exact source/evaluation refs; objective normalization only orders accepted comparable records.

Owner/consumer paths: `policy-engine/src/polisyos/scientist/methods/autotune/warm_start.py`, `policy-engine/src/polisyos/scientist/methods/search/strategies/transfer.py`, `policy-engine/src/polisyos/scientist/methods/autotune/bayesian_generator.py`.

Эти из перечисленных product paths действительно входят в source-delta 6ac: `policy-engine/src/polisyos/scientist/methods/autotune/bayesian_generator.py`, `policy-engine/src/polisyos/scientist/methods/autotune/warm_start.py`, `policy-engine/src/polisyos/scientist/methods/search/strategies/transfer.py`. Остальные — названные upstream/live consumer paths; это не утверждение, что они были изменены.

**Команда на post-integration freeze (не запускалась этим аудитом):**

```sh
cd policy-engine && python -m pytest -q tests/unit/scientist/methods/search/strategies/test_transfer.py tests/unit/scientist/methods/autotune/test_warm_start.py tests/unit/scientist/methods/autotune/test_transfer_workflow.py -ra
```

**Независимый oracle:** Exact ArtifactRef→WarmStartBridge→Bayesian runner; independently compare normalized objective/quota and real GP training corpus.

<a id="bundle-trn-02"></a>

### TRN-02 — Точные snapshot-refs и атомарное поколение vector memory

Finding IDs: B129, B133, B134.

Выбранный путь: `FileSystemCAS` и composite immutable `ArtifactRef` — существующая identity полного persistent generation. В памяти собрать frozen `{dim,index,keys,metadata,key_to_idx,ref/version}` и публиковать одним pointer swap после успешного load/add; `query` захватывает pointer один раз. Если локальному result cache нужно хранение, ключ — полный immutable ArtifactRef + schema version, value immutable/copy-on-read, LRU максимум 128 entries и 32 MiB serialized payload; oversized item обходит cache. Не добавлять второй `current-generation` pointer. Distributed/latest-pointer semantics вне bounded profile.

Альтернатива, которую здесь не выбираем: Не повышать ANN `top_k` ради известного exact ref; не вводить generation manifest/latest authority при существующем composite ref; не использовать mutable run_id как artifact identity.

Проверка корректности/сопровождения: Barrier-controlled reader interleaves query с load/add старого/нового поколения, у которых различаются key/coordinates/metadata; result triple целиком old либо new. Cache cold/warm по exact ref сохраняет content; тот же run_id с новым ref не alias-ится; caller mutation не меняет cache; eviction и byte bound проверяются. Exact known ref вне ANN top-k читается напрямую через CAS. Второй процесс повторно открывает exact pinned ArtifactRef, не mutable latest pointer.

Owner/consumer paths: `policy-engine/src/polisyos/scientist/agent/vector_memory.py`, `policy-engine/src/polisyos/scientist/methods/search/strategies/transfer.py`, `policy-engine/src/polisyos/core/artifacts/store.py`.

На G97 `FileSystemCAS` хранит immutable CAS objects (`core/artifacts/store.py@97c85fae:403–414`), а `VectorMemoryStore.save_to_artifact` возвращает composite bundle ref (`scientist/agent/vector_memory.py@97c85fae:173–215`). Текущий `query` читает `_keys/_index/_metadata` отдельно, а `load_from_artifact` меняет generation fields последовательно (`:160–171,217–256`); barrier oracle проверит shared-object race, которого rollback test не закрывает.

**Команда на post-integration freeze (не запускалась этим аудитом):**

```sh
cd policy-engine && python -m pytest -q tests/unit/scientist/agent/test_vector_memory.py tests/unit/remediation/test_trn_02.py tests/unit/scientist/methods/search/strategies/test_transfer.py -ra
```

**Независимый oracle:** Старый/новый reader result никогда не смешивает key-distance-metadata; exact-ref warm/cold/mutation/eviction/memory controls зелёные. Если snapshot mechanism удалить при сохранённых markers, barrier oracle должен получить неверную mixed tuple или ошибочное cache admission.

<a id="bundle-trn-03"></a>

### TRN-03 — Контекст переноса, фильтры lessons и время подтверждения

Finding IDs: B135, B136, B137.

Выбранный путь: Сначала извлечь типизированный base TransferContext, затем разрешить overrides/default; применить одинаковые filters после transfer/materialize. Last-access хранить как retention, evidence time — только при producer/revalidation.

Альтернатива, которую здесь не выбираем: Do not let truthy defaults erase fields already present in typed context; do not let LRU access refresh evidence freshness/trust.

Проверка корректности/сопровождения: Same query predicate on local and transferred results preserves requested scope; provenance time and retention time are different semantics.

Owner/consumer paths: `policy-engine/src/polisyos/scientist/methods/search/lessons.py`.

Эти из перечисленных product paths действительно входят в source-delta 6ac: `policy-engine/src/polisyos/scientist/methods/search/lessons.py`. Остальные — названные upstream/live consumer paths; это не утверждение, что они были изменены.

**Команда на post-integration freeze (не запускалась этим аудитом):**

```sh
cd policy-engine && python -m pytest -q tests/unit/scientist/methods/search/test_lesson_query_persistence.py tests/unit/scientist/search/test_lessons.py tests/unit/scientist/search/test_lesson_transfer.py -ra
```

**Независимый oracle:** Actual query/materialize/persist for object and JSON context; same filters local/transferred, ordinary reads cannot renew verification clock/trust.

## Все 45 finding rows: bounded result и конкретный остаток

В таблице bounded result означает только то, что именно записано в candidate receipt; каждая строка остаётся `partial`. Следующий input/owner — конкретная незакрытая часть, а не общее разрешительное условие. Полные оригинальные критерии читаются по immutable criterion refs из coverage.json. Выбранный следующий маршрут, consumer, oracle, negative control и command находятся в разделах выше и compact per-ID selected_plan_not_executed; raw candidate outputs этим индексом не заменяются.

| ID / bundle | Что действительно ограничено candidate witness | Что требуется закрыть дальше; конкретный владелец |
|---|---|---|
| `B41` / `STP-01` — Сбой текущего измерения сходства может подтвердить сходимость по старым векторам | Existing current embedding/model/dimension freshness admission retained. | Accepted historical four-base replay and actual embedding profile inputs remain separately bounded. **Владелец:** Convergence profile/threshold owner; no general embedding equivalence supplied. **Gap:** `verification_missing`. |
| `B106` / `STR-01` — Ограничение списка замечаний меняет численную оценку устойчивости | Candidate bounds issue payloads and counts observed occurrences before cap; selected empirical fraction still needs acceptance. | Считать finite-evaluated scenarios и per-scenario violations до grouping/top-k; показывать `(finite_evaluated−violated)/finite_evaluated`, unknown/completeness отдельно, zero denominator unavailable, incomplete run partial. Это observed-sample fraction, не population probability. **Владелец:** STR runtime owner; G acceptance. **Gap:** `semantic_test_missing`. |
| `B107` / `STR-01` — Стресс-поиск выбирает максимум показателя, чьи низкие значения признаны уязвимостью | Real typed GDP maximize/budget minimize normalization and adaptive extremum agree with physical-coordinate DGP; invalid evidence and CAS readback retain the bounded report semantics. | Accepted historical four-base/finding-level verification and production distribution inputs remain absent; bounded empirical extrema do not establish whole-domain failure probability. **Владелец:** Appointed STR-01 finding-level verification owner and G; STR/numerical objective runtime owner for any additional production input contract. **Gap:** `verification_missing`. |
| `B108` / `OPT-01` — Допустимое альтернативное поле дефицита игнорируется при отсутствии основного | Existing deficit alias/conflict/finite extractor retained. | Typed unit input and actual served BudgetDeficitObjective caller remain absent. **Владелец:** Objective/input owner must define admissible units. **Gap:** `consumer_missing`. |
| `B109` / `OPT-01` — Ускоренный Pareto-отбор сохраняет точку, уже доминируемую предыдущей группой | Strict Pareto comparator/coordinate artifact retained; derived HV unavailable now usable. | Run/tenant/cell-bound Pareto provider is not wired from ExecutionContext/workflow construction to served frontier publisher. Literal source census only. **Владелец:** A workflow/provider appointment and actual ArtifactStore-bound bridge; D supplies mathematical/snapshot contract. **Gap:** `implemented_but_not_orchestrated`. |
| `B110` / `OPT-01` — Название метрики не сохраняет идентичность координаты Pareto | Typed metric/split/unit/direction IDs remain content-bound across front/is_dominated. | Accepted historical selector reconciliation/four-base replay not performed here. **Владелец:** G verifies finding-level evidence acceptance. **Gap:** `verification_missing`. |
| `B111` / `OPT-01` — Неизвестная или non-finite метрика проходит в численное сравнение без отдельного состояния | Finite derived HV overflow now null with typed unavailable reason; front membership preserved. | Independent complete source-feasible/unknown producer and bridge absent; ordinary builder still self-derives source denominator. Served champion accepts nonfinite/overflow ranking. Additional independent review residual: persisted snapshot schema_version3.0 is currently admitted; D registry/G profile acceptance must supply explicit known-version admission contract and refusing control. **Владелец:** A owns served builder/node; surgical proposed129line patch is supplied, not applied. D registry/G profile acceptance for persisted unknown snapshot version admission. **Gap:** `bridge_missing`. |
| `B112` / `OPT-02` — Bayesian-обёртка предоставляет не тот SearchSpace, который потребляет оптимизатор | Autotune adapter inherits entire NativeSearchSpace protocol; optional dependency failure remains distinct. | Scientific live benchmark and upstream caller admission remain bounded independently. **Владелец:** Canonical optimizer owner; no new principal decision. **Gap:** `verification_missing`. |
| `B113` / `OPT-02` — История Bayesian-поиска теряет координаты, параметры и полную идентичность наблюдения | Actual physical params/full serialized IDs/direction retained; absent result excluded rather than numeric0. | Production benchmark result/history content admission requires actual dataset-specific evidence. **Владелец:** Benchmark producer/transfer owner; declared split/rule inputs only. **Gap:** `verification_missing`. |
| `B114` / `OPT-03` — Warm-start сохраняет исторические оценки, но выбранный путь обучения их не использует | Warm compatible origin-bound corpus reaches actual X/Y; candidate backend witness verifies consumer use. | Независимый fixed-parameter GP posterior oracle требуется сверх backend resume; production source corpus/origin остаётся отдельным условием. **Владелец:** Canonical GP owner и transfer content owner; G acceptance. **Gap:** `verification_missing`. |
| `B115` / `OPT-03` — Ветка «без refit» создаёт новую модель и теряет выученные параметры | Fitted model/transforms, corpora, RNG and fit counters persist in candidate backend witness. | Same-model BoTorch comparisons не исключают общую posterior/kernel/transform ошибку; нужен analytic mean/full-covariance oracle и frozen-parameter append. Cross-backend bit identity/production history не доказаны. **Владелец:** Canonical GP owner; G acceptance. **Gap:** `verification_missing`. |
| `B116` / `OPT-04` — Технический champion может получить оценку другого кандидата или несопоставимого испытания | Existing registry binds run/candidate/suite/split. | Pin exact suite ArtifactRef/content, metric/profile/version и champion reevaluation при смене suite; запустить mismatch falsifiers на одном canonical owner. **Владелец:** ChampionRegistry/runtime owner; principal hold не нужен. **Gap:** `semantic_test_missing`. |
| `B117` / `OPT-04` — Атомарная запись champion-файла не делает атомарным сравнение с предшественником | Existing ChampionRegistry has cross-process local POSIX lock, reread/compare and atomic pointer replacement. | Behavioral competing-writer, coherent old/new reader and crash/promotion_basis mismatch controls pin the owner contract; distributed registry вне профиля. **Владелец:** ChampionRegistry/runtime owner; no new registry. **Gap:** `semantic_test_missing`. |
| `B118` / `CTL-01` — Новый запуск контроллера наследует прежний результат и изменяет уже выданную историю | Sole fresh per-run state/nonreentrant ownership retained. | Distributed service ownership/served HTTP dispatch not established by fixtures. **Владелец:** SearchService deployment/consumer owner; no new value rule. **Gap:** `verification_missing`. |
| `B119` / `CTL-01` — Пустой batch не расходует счётчик и не завершает цикл генерации | Permanent empty remains typed exhaustion; transient empty bounded; new StrategyError preserves actual partial result and avoids stale candidate reuse. | Bounded proposal failure does not prove complete finite domain exhaustiveness. **Владелец:** Canonical generation/lifecycle owner. **Gap:** `verification_missing`. |
| `B120` / `CTL-03` — Критерий стоимости существует, но контроллер не передаёт ему стоимость | Existing sole owner spend snapshot and stop/result accounting retained. | Real evaluator retry/cache-ledger admission and an independent production budget provider are not established by these CTL fixtures. **Владелец:** FUN/evaluator ledger provider and SearchService caller own actual spend source. **Gap:** `bridge_missing`. |
| `B121` / `CTL-03` — Обучающая история, новые вычисления и sentinel-проверки имеют несовпадающие счётчики остановки | Warm history/new-evaluation counters and sentinel exclusion remain in canonical state transition. | Complete production paired-history/evaluator receipt and cross-provider spend source not supplied. **Владелец:** TRN/FUN producer owners plus native counter owner. **Gap:** `verification_missing`. |
| `B122` / `STP-01` — Достигнутый ноль превращает ухудшение в бесконечное «улучшение» критерия плато | Candidate marks nonfinite improvement unavailable, but hardcoded near-zero branch does not implement selected profile. | Реализовать versioned `abs_tol=0.01` objective units, `rel_tol=0.01`, signed direction-normalized gain, `gain ≤ max(abs_tol, rel_tol×|historical_best|)`; без unit не заявлять convergence. **Владелец:** stopping/runtime owner; principal threshold hold не нужен. **Gap:** `semantic_test_missing`. |
| `B123` / `CTL-03` — Ошибка проверки присутствующего typed-результата превращается в отсутствие typed-результата | Existing `test_malformed_typed_evaluation_cannot_fall_back_to_legacy_objective` asserts malformed-present leaves `best_candidate is None` and keeps invalid reason; absent typed input preserves legacy path. | Reference that actual SearchLoop consumer test from CTL-03 and rerun at accepted integration SHA. No publication/promotion authority claim or owner-permission dependency belongs here; B164 owns that boundary. **Владелец:** SearchLoop/typed-evaluation consumer for integration; G acceptance. **Gap:** `verification_missing`. |
| `B124` / `CTL-02` — Эвристика «волатильных» полей удаляет содержательные даты внутри кандидата | Semantic action dates stay in canonical candidate identity; trace-only metadata excluded. | Dynamic foreign datetime serialization and other cache identities are owned by FUN; no general time-law claim. **Владелец:** Canonical action identity owner. **Gap:** `verification_missing`. |
| `B125` / `CTL-02` — Сериализуемое состояние стратегии не восстанавливает собственный Python RNG после JSON | Python/wrapper RNG plus nested base restore fixed; shared malformed artifact decoder widened; GP intrinsic stream used. | Literal production RL wrapper construction not found; reflective/external invocation and production wrapper checkpoint caller not established. **Владелец:** Control/RL production route owner must wire admitted caller; G acceptance separate. **Gap:** `verification_missing`. |
| `B126` / `CTL-02` — Соболь-последовательность зависит от заполнения кэша и не включена в checkpoint | Sobol logical prefix/cursor/seed/backend/space + wrapper/base counters retained; attainable projection policy in fingerprint. | Production wrapper lifecycle/accepted legacy replay boundary remains separate. **Владелец:** Canonical checkpoint/Sobol caller owner. **Gap:** `verification_missing`. |
| `B127` / `OPT-02` — Разные непрерывные координаты обозначают одно и то же дискретное исполнение | All proposal factories bind executed normalized coordinates, retain relaxed proposal; duplicate pending/completed/batch exact physical action; attainable finite domains enforced. | Full admitted production checkpoint workflow/independent transfer source content still needs actual caller evidence. **Владелец:** Canonical effective-action owner with explicit projection and GP replay policy bindings. **Gap:** `verification_missing`. |
| `B128` / `TRN-01` — При восстановлении найденных оценок несовместимый конструктор молча удаляет все строки | typed faithful restore, canonical CAS encoder/decoder, original timestamp and record diagnostics | representative live history not supplied **Владелец:** transfer runtime; G decides closure after combined/local evidence **Gap:** `verification_missing`. |
| `B129` / `TRN-02` — Точная ссылка на найденный запуск теряется, а история заново ищется среди соседей нулевого вектора | exact discoveryArtifactRef retained; typed unavailable/corrupt/schema reasons and discovered-ref issues | no live history availability receipt **Владелец:** transfer runtime **Gap:** `verification_missing`. |
| `B130` / `TRN-01` — Ограниченный перенос выбирает худшие нормализованные оценки вместо лучших | normalized ascending ranking, valid-source round-robin quota, rejected diagnostics outside numeric capacity | production acceleration/solution-quality benchmark absent and unclaimed **Владелец:** transfer runtime **Gap:** `verification_missing`. |
| `B131` / `TRN-01` — Похожесть запуска подменяет достаточную привязку переносимой численной оценки | full target/source basis, CAS-envelope reconciliation, resolve-and-content-bind original record/context | actual execution-owner tenant authorization and live source metadata/provenance validation remain unestablished **Владелец:** transfer compatibility runtime plus institutional data/execution owners **Gap:** `bridge_missing`. |
| `B132` / `TRN-01` — Обратный warm-start-мост создаёт фиктивный benchmark вместо сохранения происхождения | reverse path resolves original benchmark and candidate; source loop/suite/split/values retained; historical view nonpromotable | real-source benchmark/evaluator validation remains localG queue **Владелец:** transfer lineage runtime **Gap:** `verification_missing`. |
| `B133` / `TRN-02` — Кэш истории привязан к изменяемому run_id, а не к версии её артефакта | Exact immutable refs available; cache warm/cold, mutation and memory bounds not fully established on canonical consumer. | Ключ full ArtifactRef/schema, immutable/copy-on-read LRU ≤128 entries/32 MiB, oversized bypass. Тесты same-run-id/new-ref, warm/cold, mutation, eviction/byte cap; distributed/latest-pointer вне профиля, principal hold не нужен. **Владелец:** Transfer runtime/cache owner; G acceptance. **Gap:** `semantic_test_missing`. |
| `B134` / `TRN-02` — Ошибка нативного индекса публикует несогласованные векторы и метаданные | native/Python generation integrity plus complete canonical metadata roundtrip | owner-issued live transfer metadata remains pending **Владелец:** Transfer metadata issuer/data owner **Gap:** `verification_missing`. |
| `B135` / `TRN-03` — Переданный типизированный контекст теряет task_family и domain при разрешении значений | Existing typed/JSON substantive task_family/domain context reaches the actual SearchController generator lesson_hints consumer; characterized at slice base, not newly repaired. | Real tenant authorization, production lesson history and accepted historical four-base replay not supplied; no new scientific evidence-sufficiency/revalidation authority. Retention is best effort across processes; partial-answer local+transfer dedup is outside slice. **Владелец:** Transfer replay/custody and native lesson consumer owner for production integration; E/scientific evidence owner for any revalidation contract; G for finding acceptance. **Gap:** `verification_missing`. |
| `B136` / `TRN-03` — Ограничения запроса к урокам действуют локально, но теряются на ветви переноса | Shared before/after effective-card projection applies query filters before transfer materialization and afterward; newest producer CASref/candidate basis survives older arrivals, and explicit active TTL is used on all retrieval routes. | Real tenant authorization, production lesson history and accepted historical four-base replay not supplied; no new scientific evidence-sufficiency/revalidation authority. Retention is best effort across processes; partial-answer local+transfer dedup is outside slice. **Владелец:** Transfer replay/custody and native lesson consumer owner for production integration; E/scientific evidence owner for any revalidation contract; G for finding acceptance. **Gap:** `verification_missing`. |
| `B137` / `TRN-03` — Обычное чтение старого урока восстанавливает уверенность без новой проверки | Evidence age derives from producer version time and max producer last_seen; reads only write separately throttled retention hints and cannot rejuvenate confidence. Newest artifact selection and active policy remain coherent across reopen/transfer. | Real tenant authorization, production lesson history and accepted historical four-base replay not supplied; no new scientific evidence-sufficiency/revalidation authority. Retention is best effort across processes; partial-answer local+transfer dedup is outside slice. **Владелец:** Transfer replay/custody and native lesson consumer owner for production integration; E/scientific evidence owner for any revalidation contract; G for finding acceptance. **Gap:** `verification_missing`. |
| `B156` / `FUN-01` — Кэш ticket объединяет разные контексты и калибровочные роли | bounded_verified: same effective request reuses terminal result; dataset/model/role/sentinel/rule/time changes isolate fresh work; typed date/datetime preserved recursively. Prior ordinary attempt remains unchanged. | Transferred source cells are compact PASS observations without raw archives. No production history/reuse receipt supplied. **Владелец:** None invented for fixture cache separation; G accepts finding scope. Persisted cross-process cache/history compatibility remains runtime owner A/D input requirement. **Gap:** `verification_missing`. |
| `B157` / `FUN-02` — Сокращённая конфигурация L3 меняет вход последующей L4 | bounded_verified existing mechanism: L3 copies caller configs; L4 direct and L3->L4 retain full effective settings/output. | Production _PolicyRuntimeWorkflowEngine pins backend fidelity but ignores generic data/bootstrap config. Native production sample/draw counts and artifact/history evidence absent. **Владелец:** Native backend/evaluator owner B with policy caller A must define and measure effective reduced/full configurations before claiming production reduction. **Gap:** `bridge_missing`. |
| `B158` / `FUN-01` — Разбиение Stage A/B меняет обязательный переход после L2 | bounded_verified: full and split stop before the same unaffordable next stage and preserve routing reason/progress. bridge_missing: reported stage cost does not debit supplied BudgetState. | Authoritative live cost/reservation/reconciliation receipt and production RunPolicyBlueprint caller budget bridge absent. Native node constructs no supplied budget_state and writes trace cost only. **Владелец:** A/runtime resource-budget owner must appoint one authoritative charge bridge without estimated-cost self-attestation or double charge; D continues against that contract. **Gap:** `bridge_missing`. |
| `B159` / `FUN-01` — Временное defer или freeze закрывает ticket без доступного продолжения | fixed_bounded: spent-only hash changes cannot skip a stage-owned defer. Scheduler budget pauses resume only on improved remaining capacity or lifted freeze and rerun scheduling; lineage/trace/cost retain predecessor progress. | No authoritative real-charge bridge; no reevaluable prerequisite discriminators for stage-owned defer/retry_cheaper/high-timeout blockers. **Владелец:** Stage owner must provide an existing allowed recheck condition before those pauses can resume. No novel resume event semantics or authorization invented. **Gap:** `bridge_missing`. |
| `B160` / `FUN-02` — Пустая воронка выдаёт положительный численный результат | bounded_verified existing mechanism: empty/capped output stays not_evaluated; a genuinely completed numerical zero remains zero. | All publication/dashboard consumers and production persisted empty-run projections not admitted. **Владелец:** G accepts bounded funnel behavior; A owns any further operator/registry projection integration. **Gap:** `consumer_missing`. |
| `B161` / `FUN-03` — Ранняя неоценённость навсегда доминирует над поздним уточнением | partial: semantic request identity now prevents foreign rule/time reuse. Selective same-scope refinement not established: historical merge_max remains; uncertainty_current feedback is only final stage envelope. | Content-bound estimate provenance and existing allowed procedure/supersession contract to distinguish refinements from independent constraints or foreign population. No downstream production rejection caused by historical max reproduced. **Владелец:** D/scientific uncertainty owner with E/calibration and A/evidence consumer must appoint same-subject/value/input/rule/time basis and allowed refinement relation. Do not global min/last, overwrite independentrisk, or invent authority. **Gap:** `semantic_test_missing`. |
| `B162` / `FUN-02` — Некорректная ширина интервала выглядит как нулевая неопределённость | bounded_verified existing mechanism: missing/invalid CI width yields conservative typed uncertainty; valid0 retains zero-width method while numerical output remains. | Real native evaluation adapter output encodings beyond bounded fixture numbers/strings and production estimator data absent. **Владелец:** B/numerical evaluator owns any additional output-format contract; G accepts bounded typed normalization. **Gap:** `producer_missing`. |
| `B163` / `FUN-03` — Один tracker без наблюдений одновременно сообщает normal и no_promotion | bounded_verified existing mechanism: empty tracker reports not_established/no_promotion without measured drift; aligned and opposite observed corpora have coherent metrics/routing; compatible native snapshot loader reuses real stage pair observations. | Production calibration report scope/content admission, natural observed corpus and source evaluator history absent. **Владелец:** E/calibration owner with A/native caller must admit snapshot subject/run/config scope; metrics labels and persisted fixture are not evidence authority. **Gap:** `producer_missing`. |
| `B164` / `FUN-03` — Запрет продвижения проверяется после вызова потенциально записывающего runner | Candidate preflight/native guard blocks known unsafe modes, but generic permission is still self-attested bool. | Typed owner-issued permit, independent current verifier and commit-time generation/revocation check отсутствуют; keep `bridge_missing`. С absent/fake/wrong issuer/candidate/run/ticket/purpose/expired/revoked-after-preflight при bool marker true writer должен иметь zero effects. **Владелец:** A/B existing permission/write owner; D consumes, не invent subsystem. **Gap:** `bridge_missing`. |
| `B165` / `FUN-02` — Промежуточный APPROVE переживает итоговый defer | bounded_verified existing mechanism: aggregate verdict follows ticket decision; optional local L2 verdict survives as stage_verdict and does not change aggregate DEFER. | Sibling operator/registry compatibility consumers and production histories not selected. **Владелец:** A owns dependent compatibility projection admission; no technical promising flag grants publication authority. **Gap:** `consumer_missing`. |
| `LA-014` / `SRV-01` — Search contracts импортируют и изменяют legacy runtime | Contract-only imports stay lazy; native ask/tell state owner and SearchLoopRunner route exist. | Appointed production SearchService consumer/migration owner and served request/readback/retirement contract absent. **Владелец:** Owner appointment typed blocker retained. **Gap:** `implemented_but_not_orchestrated`. |
| `LA-015` / `SRV-03` — SearchController: живое legacy-ядро, требующее поэтапного замещения | Live SearchLoopRunner uses _NativeSearchServiceDriver; sole canonical state transitions retained. | Full end-to-end trace equivalence across agreed historical reader window, retirement/rollback and production evaluator-failure/resume deployment are not established. **Владелец:** Native lifecycle engineering owner plus migration owner; no blanket local-data debt. **Gap:** `verification_missing`. |

## Зависимости и порядок действий

1. **Сначала принять конкретный D source candidate или отдельный проверенный forward port в интеграцию.** G должен сам review exact 6ac diff от D slice-base и exact output blobs на target G97, затем определить обычный append-only integration result. Кандидат не ancestor G97; переприменение патча к c40 не подтверждает применимость к G97. Сохранить ранее интегрированные изменения в пяти кодовых путях, изменившихся после D-старого G checkpoint (из D receipt: calibration continuous/curve, catalog causal README, backtesting bootstrap, composition bridge). После freeze перечитать branch, source paths и tree с интеграционного target.

2. **Потом D/A provider bridge для Pareto/HV (B109/B111).** Перед применением `search-A-owner-dependency.patch` принять D `hypervolume_assessments_by_view` contract/schema: patch имеет apply-check только на c40 и предложенный output ссылается на этот новый metadata. Затем A назначает источник реальных run/tenant/cell-bound objective values и wires provider через builder/node/CAS consumer (`scientist/policy_design/output.py`, `nodes/builtins/planning/run_hierarchical_policy_search.py`). Положительный тест проходит actual run-context до published frontier; deletion/fake denominator, absent/unknown/nonfinite/overflow cases должны fail-closed. Patch в receipt — `proposed/not_applied`, runtime-tested=false; не заявлять capability по одному чистому `git apply --check`.

3. **После source freeze выполнить bundle commands из таблицы на точном integration SHA.** GP-witness и transfer-consumer suites запускаются на CPU с установленными и зафиксированными Torch/BoTorch/GPyTorch версиями. Нельзя называть dependency missing успешным skip. Acceptance отчёт сохраняет полный argv, interpreter/backend, SHA/tree, output и исходный/negative-control результат. Отдельно исправить residual architecture gate, не подменяя source integration.

4. **Локальная G-проверка остаётся локальной и read-only для production.** D receipt указывает exact findings `B113, B114, B115, B128, B130, B131, B132, B134`: нужны original candidate/evaluation CAS/history, source/target bounds, units, objective/directions, split, origin/tenant и фактический evaluator; снова запустить native configured consumer и сравнить реальную lineage/measurements. Аналитическая transfer fixture подтверждает мост, а не историю и не advantage. Production data не переносить в эту папку и не загружать.

5. **Применять выбранные bounded profiles и проверять их на назначенных owners.** Для `B106` считать `(finite_evaluated - violated_scenarios) / finite_evaluated` до grouping/top-k, а attempted/unknown/completeness держать рядом; это доля наблюдённых finite outcomes, не population probability. Для `B116/B117` применять exact suite ArtifactRef/content basis и существующий ChampionRegistry lock/CAS/read/crash contract; второй registry и distributed guarantee не входят в profile. Для `B122` проверять direction-normalized `abs_tol=0.01` objective units плюс `rel_tol=0.01`, с отсутствующей unit как no-convergence-claim. Для `B133` применять exact immutable ArtifactRef keyed cache, immutable/copy-on-read values и explicit local LRU ≤128 entries/32 MiB; distributed latest-pointer semantics вне profile. Для `B134` transfer metadata issuer выдаёт live owner-bound generation record. Для `LA-014` назначается миграционный owner; contract import purity сама не переключает production caller. Для `LA-015` снимается историческая trace equivalence, аварийный resume и поддерживаемая rollback boundary.

6. **Funnel residuals закрываются действительными producers/consumers, не исправлением prose.** `B158/B159`: A/runtime resource owner даёт authoritative spend/reservation/settlement seam и permitted recheck event; текущий native node пишет trace cost, но переданный `BudgetState` не списывает stage cost. `B157`: policy backend должен применить реальную reduced/effective data/bootstrap config, а не только вернуть полный direct/L3 parity. `B161`: D/scientific uncertainty owner с E/A фиксирует одну разрешённую subject/value/rule/time refinement relation; `merge_max` не превращать ни в global minimum, ни в «последнее значение побеждает». `B162/B163`: native evaluator producer выдаёт valid uncertainty/observation records; пустая калибровка остаётся `not_established`. `B164`: D/B/A appoint owner and evidence contract, который связывает candidate+purpose+run/ticket generation+policy/time, до arbitrary effectful runner и повторно перед commit. `B160/B165`: admission расширить на конкретных publication/operator/registry consumers, если они входят в closure surface.

## Технические основания выбора

- [BoTorch v0.18.1 Model API](https://botorch.readthedocs.io/en/v0.18.1/models.html) определяет `condition_on_observations(X, Y)` как conditioning существующей модели на добавленные наблюдения с возвратом объекта того же типа. [BoTorch optimization docs](https://botorch.org/docs/optimization) отдельно определяет `fit_gpytorch_mll()` как оптимизацию GP hyperparameters. **Вывод:** продолжение обученного состояния и периодическая подгонка параметров — разные события; проверять надо настоящий model state, tensors, transforms и вызовы fit, а не одну историю или поле `model_state`.
- [SciPy `qmc.Sobol`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.Sobol.html) различает сбалансированный `random_base2(2^m)` и произвольный размер `random(n)`; также документирует RNG и `fast_forward`, `reset` и предел sequence. **Вывод:** checkpoint должен продолжать один и тот же sampler stream, но небольшой неполный budget prefix не получает заявлений о сбалансированности полного дизайна.
- [Python `random` state API](https://docs.python.org/3.14/library/random.html) задаёт `getstate()`/`setstate()` как захват/восстановление внутреннего RNG state. **Вывод:** JSON roundtrip требует проверенного/versioned codec; повтор seed не восстанавливает уже пройденное продолжение. Python versions отличаются; точная supported range должна следовать lockfile/runtime contract.

Эти upstream документы подтверждают API-значения и библиотечную механику; они не подтверждают код D или PolicyOS closure. Установленный runtime в candidate receipts — фактический compatibility evidence для двух приведённых GP profiles. Для принятого G source потребуется повторное исполнение тех же assertion sets на выбранном locked runtime.

## Pattern closure и границы вывода

Статус capability — не `closed`. Bounded typed artifacts/behavior и candidate tests существуют, но несколько цепочек ещё имеют `bridge_missing`, `consumer_missing`, `verification_missing`, `producer_missing`, `implemented_but_not_orchestrated` или `semantic_test_missing` (все 45 labels и точная причина приведены в JSON). Наиболее прикладные: `B109` global Pareto provider; `B111` served source denominator/strict schema profile; `B120/B158/B159` authoritative budget bridge; `B123` malformed-present typed evaluation must not fall back to scalar `best_candidate` (no publication-authority claim; that boundary is `B164`); `B131` execution-owner tenant admission; `B157` effective policy backend configuration; `B160/B165` publication/projection; `B162/B163` real uncertainty/calibration producers; `B164` external owner-backed effect gate; `LA-014/LA-015` live caller/cutover.

Это заключение не утверждает, что D code accepted, что production endpoint использует SearchLoopRunner, что исторические model scores истинны, что GP версии дают битовую идентичность, что HNSW имеет универсальную полноту, что cost ledger реально оплачен, что cache/distributed atomicity доказаны или что любой held semantic answer может быть заменён кодом. Каждое из них требует именно того источника/consumer/oracle, которого нет в строке residual. Все остальные локальные поведения нужно принять и перепроверить по точному candidate, а не блокировать из-за отсутствия посторонней production authority.

Построчное задание — coverage.json:selected_plan_not_executed: 17 bundle, 45 finding, точные criterion locators, selected mechanism, owner/input, consumer, oracle, negative, command и P40/P41. Candidate source comparisons/полные receipts читаются по committed refs из input-identity.json; исходные критерии и большие outputs не копируются в этот пакет.
