# RES-02 — один смысл успешного завершения и согласованный checkpoint уровня
## C66 · 1 ноября 2026 года

**Порядок:** 66/127, LANE-06. **Исходные IDs:** B72, B73. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Свежая проверка после внешнего сохранения C65.

## Решение

**9 bounded MATCH; новый подтверждённый продуктовый R не установлен.** Actual tier scheduler одинаково исключает skip из successful frontier, принимает state и completed-set после решения commit/rollback и публикует один checkpoint всего принятого уровня. Fail-fast и continue теперь сохраняют разные, но внутренне согласованные результаты.

Подтверждён ограниченный producer → journal merge → frontier → hook путь. Native CAS/head/history, останов процесса и реальное повторное открытие не исполнены. Существующие tests прочитаны; их persistence fixtures требуют согласования с текущим API. Полного закрытия нет.

## 1. Исходная матрица

| ID | Проверенный смысл | Остаток |
|---|---|---|
| B72 | P01: один и тот же typed skip остаётся skip при добавлении независимого соседа; completed содержит только ok. P03/P04: fail исключён | G01 native consumer/skip-blocker/resume; G02 tests |
| B73 | P02: первая и единственная публикация A/B содержит оба эффекта и оба aliases. P03: fail-fast rollback до публикации, continue фиксирует success. P05: legacy node-only hook не делит parallel frontier | G01 durable crash/reopen, bytes retention; G02 tests |

Полная карточка7786–7884 и existing test_res_02.py409 строк прочитаны. Появление файла не считается доказательством; ниже отражено поведение владельцев.

## 2. Skip не превращается в произведённый результат

В одиночной ветви alias добавляется только при `record.status == "ok"`, а не при отрицании fail. Parallel branch выводит tier_completed только из ok records. `_run_single_node` принимает outcome.state и вызывает checkpoint тоже только для ok. [S01:466–541](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L466-L541) [S01:1347–1395](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L1347-L1395)

**P01:** исполнен весь unchanged nested tier closure. Без соседа: skipped→after, statuses skip/ok, completed=[after], checkpoint frontier=[after]. С независимым узлом: statuses skip/ok/ok, frontiers=[independent], затем [independent,after]. Skipped отсутствует во всех completed lists. Typed NodeOutcome и NodeRunRecord настоящие; классификация skip-blocker явно fixture и не приравнена к native semantics всех optional nodes.

Это исправляет исходное различие ширины без нового словаря статусов. Не следует из этого, что любой skip обязан повторяться или что зависимый consumer уже получил все нужные outputs: условия и output contracts остаются самостоятельными правилами. Здесь не заменяли skip на ok ради зелёного теста.

## 3. Первая публикация уже соответствует целому принятому уровню

`_run_parallel_tier` собирает records, successful journal outcomes и cache refs, затем делает actual merge. Он не публикует N частичных completed lists поверх одного общего state. Outer tier сначала принимает решение о rollback/commit; только accepted successes пополняют completed_nodes и передаются одному `_handle_tier_checkpoint`. [S01:498–546](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L498-L546) [S01:1519–1600](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L1519-L1600)

**P02:** A пишетa, B увеличиваетn с0 до1. Первая и единственная captured publication содержит state{n:1,a:1}, completed=[a,b], оба cache refs и sequence1. Actual resume projection по этому completed-set даёт пустой остаток: B не возвращается в план, n остаётся1. Это witness согласованного payload **до native durability**, не выполненный kill/restart процесса.

`CASCheckpointHook.on_node_complete` делегирует tier owner; tier writer объединяет prior и current completed, сохраняет все refs одной фиксации и двигает sequence по числу новых aliases, сохраняя прежнюю нумерацию. **P08:** prior + [a,b] → [prior,a,b], одна публикация, sequence2 при start1. [S02:884–1036](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py#L884-L1036) [S02:1107–1203](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py#L1107-L1203) [S02:1285–1344](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py#L1285-L1344)

**P05:** node-only async hook при parallel tier отвергается **до первого producer**. Для serial workflow тот же legacy hook работает и получает completed=[a]. **P06:** отсутствие hook вообще не запрещает обычный успешный merge. Это узкая совместимость, а не глобальное требование нового checkpoint backend. [S01:2346–2461](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L2346-L2461)

## 4. Fail-fast и continue не смешивают принятый state с наличием артефакта

**P03:** сначала prior успешно фиксируется; следующий уровень left=ok/right=fail.

- **fail_fast:** returned state и последний captured checkpoint содержат только prior. Completed=[prior]. Нового tier checkpoint нет. Actual RollbackCompensationEvent содержит failed=[right], completed_before_tier=[prior], restored state prior — left не ошибочно включён в предыдущий frontier.
- **continue:** returned state содержит prior,left; новая публикация содержит тот же state и completed=[prior,left]. Compensation не вызывается. Right остаётся failed: частичный успех не превращает весь workflow в успех.

В обоих случаях record left сохраняет output ref. Это сохранность декларации вычисленного результата в доступном record, **не доказательство сохранности настоящих CAS bytes**: producer и storage в этом probe явные fixtures. Нельзя смешивать наличие артефакта, принятую state-write и право включения в финальные selected outputs. Current finalizer отдельно сверяет output refs с выбранным state. [S01:519–546](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L519-L546) [S01:1306–1343](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L1306-L1343) [S01:828–860](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L828-L860) [S05:202–230](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/executor.py#L202-L230)

**P04:** single fail после prior даёт тот же prior-only state/frontier и правильное completed_before_tier. **P07:** actual merge conflict A/B по одному target оставляет исходное state, completed пуст и publication count0; records превращаются в fail, но сохраняют output и diagnostic refs. Cache refs конфликтующего уровня не выдаются как accepted seed.

## 5. Status provenance и существующие проверки

Hook не должен превращать историческое state-only completed множество в доказательство native ok. **P08:** после explicit unestablished mark при наличии prior completed повторный mark не восстанавливает status contract; fresh empty frontier может установить его. Resume дополнительно отказывает completed metadata без `native_node_outcome_v1`. Existing native negative test прочитан, не выполнен. [S02:1129–1144](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py#L1129-L1144) [S02:2521–2533](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py#L2521-L2533) [S13:1065–1098](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/orchestration/engine/test_checkpoint.py#L1065-L1098)

Existing remediation файл содержит восемь native tests: single/parallel skip, atomic tier, fail-fast, continue, serial legacy, no hook, parallel node-only refusal. Все восемь **UNRUN** в штатном runtime. **P09 / G02:** реальные nested `_persist_workflow_spec` и `_persist_state` helpers не принимают current `return_selected_profile`; прямой вызов обеих даёт TypeError. Это несовместимость test harness, а не основание убирать selected-profile contract из продукта. [S06:109–113](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_res_02.py#L109-L113) [S01:305–311](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L305-L311) [S01:861–862](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L861-L862)

## 6. Границы и остаток

**G01:** выполнить общий LANE-06 integration сценарий через native local runner, реальный CAS и selected owner: останов после первой публикации, повторное открытие, отсутствие второго incrementB, согласованность head/state/completed, compensation и доступность уже вычисленных output/cache bytes. Проверить реальные optional consumers, не только fixture after без обязательного scientific input. Atomic payload сам по себе ещё не доказательство crash durability.

**G02:** согласовать существующие tests с current persistence ABI и запустить их без обхода ownership guards. Сейчас Python3.12.14 вместо3.14, Pydantic2.13.4 вместо<2.13, pytest отсутствует, public import blocked Corestore2118syntax. Это ограничения среды и qualification, не продуктовый R.

Экономия «одна публикация вместоN» подтверждена на captured calls; workload latency, объём сериализации и научная состоятельность результатов не измерены. Технический frontier помогает сохранять полезную частичную работу, но не создаёт эмпирическую authority сам по себе.

Сохранить ok-only frontier, commit decision до checkpoint, atomic tier hook, prior-only compensation и раздельное отражение output existence/state acceptance. Расширять existing owners и общий integration набор, не строить новый scheduler или новую систему статусов.

## 7. Честность исполнения

Исполнены unchanged tier closure и полные выбранные methods; реальные journal/merge/topo/state/records и hook methods. Publication/head/GC, producers и skip-blocker classification — fixtures.57 imported module identities сверены с Git, не заявлено полное human review57files.

Первая harness attempt ошибочно вернула live guarded branch, пропустив actual completion detachment; update last_checkpoint_ref был правильно отказан. Actual execute_node вызывает `_completed_producer_state` до возврата. Final fixture делает именно этот existing переход, сохраняя journal;9MATCH,exit0. Исходник и лог отказа сохранены; это не product bug и не отключение producer guard. [S01:2337–2345](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L2337-L2345) [S03:467–484](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/state_branching.py#L467-L484)

[Диагностика](../04_Проверки/C66_RES02/bounded_diagnostics.json) · [Команды](../04_Проверки/C66_RES02/commands.json) · [Границы](../04_Проверки/C66_RES02/native_verification.json) · [Источники](../05_Источники/C66_источники.json) · [Остатки](../01_Реестры/C66_остатки.json).

**66/127 пакетов рассмотрены ограниченно;155 уникальных B/LA частично оценены. Следующий — RES-03. Полного закрытия нет; фаза2 не начата.**
