# CMP-01 — effective DAG и общий payload действительно связаны с исполнителями
## C42 · 31 октября 2026 года

**Исходные IDs:** B42, B43, B44. **Порядок:** 42/127. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит.

## Решение

**Все три исторических механизма исправления присутствуют:** async class разрешается локальным импортом при вызове; build замораживает effective requires adjacency и уровни; sequential/async пользуются одним static→dynamic→override payload builder. **21 bounded MATCH / 0 ERROR**, включая actual `MethodComposer.add→build→freeze→execute`, а не вручную заданный DAG.

Новых product defects в этом ограниченном scope не установлено. **Полного закрытия нет:** native pytest/import-order acceptance заблокирована средой; fresh persisted effective-plan consumer и optional backends не аттестованы.

## 1. Матрица исходных IDs

| ID | Подтверждённая часть | Остаток |
|---|---|---|
| B42 | Lazy facade и deferred wrapper import; internal import error не сохраняется как permanent None; wrapper повторно работает | G01: оба native import order и actual built chain на поддержанном Python |
| B43 | Requires-only predecessors/successors входят в frozen DAG; уровни доступны, независимый sibling параллелен; cycle и снятие ребра отказывают до dispatch | G01 native consumer; G02 persisted plan reconstruction |
| B44 | Actual shared builder сохраняет window=20 без повторного override; scale override даёт одинаковый numerical result 60 | G01 native dispatcher/runner; G03 optional profiles |

[Полная карточка](../05_Источники/CMP-01_исходные_строки.txt), строки 5200–5324. `Не аттестовано` не означает `не реализовано`.

## 2. B42 — импорт исправлен на конкретной границе

Chain module больше не импортирует async class до carrier declaration. Оба wrapper делают local import внутри вызова; нет broad `except Exception → None`. Async module по-прежнему импортирует carrier/shared helpers из chain, но обратная зависимость отложена. Backend facade отдельно сохраняет lazy exports и различает отсутствующий submodule от внутренней ModuleNotFoundError. [S02:1–62](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/chain_executor.py#L1-L62) [S02:998–1058](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/chain_executor.py#L998-L1058) [S03:42–70](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/async_chain_executor.py#L42-L70) [S11:184–206](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/__init__.py#L184-L206)

P03/P04 исполняют actual wrappers с exact async class, экспортированным в контролируемый module seam; это не native module initialization. P16 sync wrapper внутри running event loop даёт actionable error с указанием await route. P17 injected internal import failure проходит наружу без маскировки; P18 следующий отдельный вызов успешно выполняет цепочку, permanent unavailable latch не возникает.

**Native попытки:** два свежих процесса с обратным import order оба завершились exit 1 в downstream `ir/analytics/uncertainty.py:287`: `except TypeError, ValueError` не разбирается текущим Python 3.12. Поддержанный baseline — 3.14. Этот результат **не доказывает повторный circular import и не является product FAIL**; normal import success не заявлен. [S16:279–292](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/uncertainty.py#L279-L292)

## 3. B43 — actual build сохраняет requires, не превращая его в data flow

`_requirement_edges` связывает node occurrences по объявленным FQN. Build использует эти predecessors и при topological order, и при `freeze`; frozen successors/predecessors включают ordering-only edges, а `edges` остаётся только data-flow mapping. У frozen DTO теперь есть собственный `compute_parallel_levels`. [S01:618–648](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/composer.py#L618-L648) [S01:334–367](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/composer.py#L334-L367) [S01:459–485](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/composer.py#L459-L485) [S01:735–766](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/composer.py#L735-L766)

**P01:** actual composer добавляет dependent B раньше A, плюс независимый C. Получается уровень `[A,C]`, затем `[B]`; `B.requires(A)` сохранён, data-flow edges **0**. P02 actual sequential consumer выдаёт answer 36 из sentinel 7 → A:+5 → B:×3. P03–P05 actual async/auto wrappers исполняют оба first-level узла через реальный `asyncio.to_thread` и `gather`; двухсторонний barrier завершается, значит sibling не был скрыто сериализован. B получает producer value только после завершения уровня.

Registry, materializer, dispatcher/MethodResult и reproducibility contract — явные fixtures; signatures/node/composer/graphlib/async scheduling — actual definitions. Это содержательнее fixture DAG, но **не native full backend chain**. No-dataflow empty-slot fixture не квалифицирует shape/FX/slot adapters.

P06 requires-only cycle отклоняется actual build до execution; P07 frozen snapshot не меняется при последующем добавлении узла в builder и защищает adjacency от прямой записи. P08 удаление requires edge из constructed frozen plan обнаруживается actual replay gate до первого dispatch; P09 удаление validation_context не превращает owned plan в legacy protocol bypass. P20 runtime ABI, отличный от compiled signature, также отклоняется. [S01:920–979](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/composer.py#L920-L979) [S02:337–352](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/chain_executor.py#L337-L352)

P19 missing requirement в STRICT отказывает, а OFF остаётся явно указанным `mode=off`. OFF здесь выбран ради узкого execution-contract witness и **не означает semantic/scientific approval**.

## 4. B44 — shared payload доходит до actual local execution seams

Actual `add` делит declared parameters по is_static и отказывает неизвестному authored имени. Shared `_build_node_param_payload` требует настоящий MethodNode и объединяет static, dynamic, per-call overrides именно в этом порядке. Sequential `_collect_node_inputs` и async `_dispatch_node` вызывают его; seed остаётся отдельным dispatcher argument, не подмешивается как пользовательский параметр. [S01:531–575](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/composer.py#L531-L575) [S02:355–367](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/chain_executor.py#L355-L367) [S02:415–500](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/chain_executor.py#L415-L500) [S03:367–473](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/async_chain_executor.py#L367-L473)

P10 static `window=20` без params_map даёт 40 при scale=2, а не default window=7. P11 override только scale=3 даёт **60 в обоих режимах** и равные payloads. P12 разрешённый override window=30,scale=4 даёт120. P13 actual NumPy parameter resolver отвергает неизвестный runtime override; P14 composer отвергает неизвестный authored параметр. P15 неполная untyped node projection не выдаётся за пустую static declaration. [S07:35–43](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/numpy_runner.py#L35-L43)

Dispatcher в probes — recorder, который вызывает actual `_resolve_params` и synthetic pure method. Полный MethodDispatcher/NumpyRunner прочитан на deciding boundaries, но не исполнен. Поэтому 60 — проверка передачи/арифметики fixture, не качество реального научного метода. [S08:550–857](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/dispatch.py#L550-L857) [S08:970–1032](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/dispatch.py#L970-L1032)

Ray consumer использует те же effective levels и вручную повторяет static→dynamic→override merge. Этот дубликат предпочтительно со временем заменить shared builder, но **эквивалентное копирование не объявляется само по себе дефектом**. Native Ray, JAX fusion и полная cross-backend equivalence остаются отдельно. [S10:174–226](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/ray_chain_executor.py#L174-L226)

## 5. Persisted recipe — полезная часть, не доказанный fresh executable consumer

Existing `ChainArtifact.from_chain` сохраняет stable node records, method artifact refs, data-flow bindings и execution_order; content identity и manifest input refs существуют. P21 исполняет этот producer с fixture method refs и JSON/hash seam. В resulting payload имеются 3nodes, order и 0dataflow bindings, но нет explicit effective adjacency. [S13:94–176](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/artifacts/_chain.py#L94-L176) [S13:245–292](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/artifacts/_chain.py#L245-L292)

Это **G02, не доказанный product defect**: constraint может переноситься через resolved method artifacts и восстановление compiler owner; такой полный fresh reconstruction/readback здесь не выполнен. Нельзя объявлять recipe отсутствие второго executor, коллизию всей artifact identity или полную потерю requires во всём product graph. Следующий проверяемый остаток — existing persisted spine → fresh compiler/consumer с сохранением requires-only ordering/parallel levels и edge-removal negative, а не новый paperwork architecture.

## 6. Tests, команды и продолжение

Полный `test_cmp_01.py` прочитан: настоящие fresh process import orders, built requires chain, cycle, frozen levels и static window case; native pytest BLOCKED до collection (`No module named pytest`). Два первых внешних harness запуска остановились из-за неполного source range, затем logger seam. Исправлен только audit harness; все failed logs сохранены. Третий полный запуск — **21 MATCH / 0 ERROR**. Репозиторий чист, зависимости не менялись.

Сохранить current lazy imports, actual effective DAG, replay gate, shared payload и работающий sequential contour. Продолжить с **CMP-02**: unique slot producer и occurrence-based ordering, не объявляя tag heuristics универсальными методологическими законами.

[Диагностика](../04_Проверки/C42_CMP01/bounded_diagnostics.json) · [Команды](../04_Проверки/C42_CMP01/commands.json) · [Native границы](../04_Проверки/C42_CMP01/native_verification.json) · [Источники](../05_Источники/C42_источники.json) · [Остатки](../01_Реестры/C42_остатки.json).

**42/127 пакетов рассмотрены ограниченно; 101 уникальный B/LA частично оценён. Полного закрытия нет.**
