# EXE-02 — readiness без снятия содержательных границ tier
## C64 · 1 ноября 2026 года

**Порядок:** 64/127, LANE-06. **Исходный ID:** B77. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Свежий проход после внешнего сохранения C63.

## Решение

Ограниченный readiness path существует в actual executor и действительно запускает successor после собственных predecessors, не дожидаясь независимого соседа. Tier barrier не убран глобально: checkpoint, provenance, compensation, fail_fast, conditions, semaphore timeout и unordered state overlap возвращают прежний маршрут.

**8 bounded MATCH;5 unchanged readiness regression bodies PASS. C64-R01:** textual overlap сравнивает spelling сегментов, а actual list reader/writer преобразует index через int. Поэтому `.0` и `.00`/`.+0`/`.-1` могут ошибочно считаться независимыми. Это воспроизведено через **unjournaled adapter completion**; enforced tracked producer route не обвинён. Native lifecycle и existing integration helper compatibility остаются открытыми.

## 1. Исходное требование B77 и два уровня результата

| Требование | Свежая проверка | Остаток |
|---|---|---|
| C(A) стартует до независимого B | P04 actual unchanged readiness closure, controlled events, C получает committed A | G01 public lifecycle, workload cost |
| Реальное B→C возвращает join | P04 C не стартует до B;1call каждого, seed1234 сохранён | G01 scientific method corpus |
| Не снимать semantic tier boundary | P02 hooks/conditions/policy/overlap refusal; P03 atomic hook admission | G01 native checkpoint/provenance |
| Не терять current state и не принимать hidden writes | P01 five existing state-boundary bodies; P05 failed predecessor/independent success; P07 cancellation | R01 semantic path identity; G01 full persistence |

Полная карточка7597–7665 прочитана. В отличие от ряда прежних пакетов, предложенный `tests/unit/remediation/test_exe_02.py` **действительно существует**; рассмотрено его содержание, не только имя.

## 2. Граница применимости установлена до scheduling

`_can_use_readiness_schedule` требует continue policy, отсутствие checkpoint/provenance/compensation/condition/semaphore-timeout semantics и actual NodeSpec. Для unordered pairs проверяются write/write и write/read пересечения; transitive explicit dependency даёт ordering, поэтому такая пара не обязана быть disjoint. [S01:937–1017](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L937-L1017)

**P02:** disjoint A,B,C(A) admitted; каждый hook, fail_fast, condition, unordered write/read и write/write отдельно отказывает readiness. Добавленная настоящая B→C связь допускает ordered readiness, но не ранний C. Это корректная условная оптимизация, а не незавершённость лишь потому, что не все workflows ускорены.

**P03:** actual checkpoint shape guard отказывает node-only hook для parallel tier и принимает on_tier_complete. Native CASCheckpointHook сохраняет merged tier как один frontier. Эти semantics не следует заменять per-completion checkpoint только ради раннего C. Реальная публикация hook не выполнялась. [S01:2346–2461](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L2346-L2461) [S05:1146–1203](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py#L1146-L1203)

## 3. Producer → committed state → successor

Readiness выбирает pending nodes с settled dependencies, запускает не более max_parallelism и ждёт FIRST_COMPLETED. На successful completion сначала проверяет declared delta и merge в актуальный state, затем помечает alias settled и разблокирует successors. Records выдаются в deterministic invocation order, а не случайном completion order. [S01:559–798](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L559-L798)

**P04:** выполняется весь unchanged nested closure, помещённый в явную outer fixture; actual state/branch/merge/topo owners настоящие. Два workers: A завершён, B удерживается event, C зависит только отA. C стартует до освобождения B и получает `c_input=from-a,seed=1234`. С добавленным B→C C остаётся pending до releaseB. В обоих случаях a/b/c вызываются ровно по одному разу, final state содержит все полезные поля, records идутa,b,c. Это крошечный schedule witness, **не измеренный speedup17→10 или workload benchmark**.

**P01:** пять unchanged regression bodies подтверждают separate launch baseline, deep nested isolation, refusal journal operation вне declared paths, rebase stale sibling snapshot только по declared delta и refusal undeclared unjournaled write. Actual launch pair делает две отдельные snapshots, не разделяет mutable nested inputs с current/baseline. [S01:1042–1149](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L1042-L1149) [S06:165–263](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_exe_02.py#L165-L263)

**P05:** failedA блокируетC, independentB сохраняет `b=kept`, completed=[b]. Это текущий memory state результат, не сохранённый CAS frontier. **P07:** cancellation readiness task отменяет и awaits обоих running children; их finally выполнены, C не запускался. Не утверждается preemption underlying thread или уничтожение уже произведённого внешнего эффекта.

## 4. C64-R01: строковый путь не всегда равен identity mutable target

Admission разбивает путь на строковые сегменты и сравнивает префиксы. `_readiness_get_path` и state_merge reader/writer, напротив, при list применяют `int(part)`. Unjournaled adapter получает synthetic exact-path journal по declared spelling; semantic container identity до disjointness не нормализуется. [S01:980–1017](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L980-L1017) [S01:1036–1040](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L1036-L1040) [S01:1152–1234](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L1152-L1234) [S03:404–469](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/state_merge.py#L404-L469)

**P06:** три controlled cases: writes `params.items.0` и соответственно `.00`, `.+0`, `.-1` на одноэлементном list[0]. Actual admission во всех случаях разрешает readiness. Оба producer fixtures получают launch value0; A записывает1 и commit, затем B со stale baseline записывает2. Actual unjournaled outcome preparation/merge принимают обе completions как ok; final list[2]. Пересекающиеся writers ошибочно отнесены к доказанно disjoint.

Отрицательный контроль: dict keys"0" и"00" действительно различны. Поэтому нельзя просто приводить **все** сегменты к int: correction должна учитывать тип контейнера либо на admission явно отказывать неоднозначному list spelling.

**Severity medium, confidence high bounded.** Маршрут — существующий unjournaled adapter fallback с actual ExperimentState, synthetic journal и merge. Enforced tracked producer может записать canonical path и отказать несовпадающей декларации; его обход не показан. Не утверждается production incident, security exploit или потеря настоящих научных данных. Но именно readiness predicate должен доказать независимость до снятия barrier; наличие другого более строгого маршрута не делает данный допустимый fallback независимым.

Минимальное направление — согласовать path admission/overlap/resolution через существующих owners, сохраняя dict semantics и real dependencies. Пока target identity не доказана, оставить tier boundary. Не нужен новый scheduler или увеличение worker-count.

## 5. Existing tests: полезная часть работает, native helper ABI устарел

Полный existing remediation файл321 строк прочитан. Пять static state-boundary bodies выполнены unchanged. Три async integration bodies используют helper `_executor`, который подменяет persistence methods функциями без `return_selected_profile`. Current actual `_execute_admitted` передаёт этот keyword при workflow spec и selected state persistence. [S06:63–88](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_exe_02.py#L63-L88) [S01:305–311](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L305-L311) [S01:861–875](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py#L861-L875)

**P08:** реальные existing helper definitions вызваны с current keyword; оба дают **TypeError: unexpected keyword argument return_selected_profile**. Это **C64-G02**, несогласованный test harness и препятствие будущей native qualification, не доказательство неисправности продуктового selected-profile API. Полные три integration bodies не запускались; их дальнейшие исходы не выдумываются. Нельзя убирать ownership keyword из продукта, чтобы старый mock снова стал green.

Separate native test_async_executor witness с controlled slow/quick/after_quick и checkpoint hook tests тоже прочитаны. Они остаются UNRUN, не приравниваются к нашему extracted closure.

## 6. Предел содержательной способности и следующий шаг

Local runner реально потребляет этот executor; public lifecycle всё ещё создаёт verified selected artifacts, report/finalization и run outputs. Our closure fixture намеренно не выдаёт эти внешние границы за пройденные. **G01:** pytest отсутствует; public import blocked Corestore2118 Python3.14 syntax под3.12.14; Pydantic2.13.4 вне pinned<2.13. Нет native CAS/checkpoint/provenance/fresh recovery evidence.

Bounded readiness расширяет полезный цикл — независимый successor раньше получает committed inputs без изменения числа научных повторов. Однако state read/write declarations не доказывают полноту hidden external-effect dependencies; неизвестные semantics требуют прежней conservative границы. Нет empirical authority, общего workload speedup или подтверждения seed/distribution equivalence для всех методов. Cost двух snapshots тоже надо измерить, а не обещать экономию RAM.

Сохранить narrow readiness path, actual current-state delta ownership и semantic tier fallback. Исправить R01, согласовать existing test helpers и выполнить общий execution/resume integration набор после разрешённых native prerequisites. Отсутствие универсального deterministic model inventor не относится к дефектам B77.

Initial7observations и final8observations run оба exit0; исходники/logs обоих сохранены. Repo чист; installs/source edits нет. MATCH R01 означает воспроизведение остатка, не product PASS.

[Диагностика](../04_Проверки/C64_EXE02/bounded_diagnostics.json) · [Команды](../04_Проверки/C64_EXE02/commands.json) · [Границы](../04_Проверки/C64_EXE02/native_verification.json) · [Источники](../05_Источники/C64_источники.json) · [Остатки](../01_Реестры/C64_остатки.json).

**64/127 пакетов рассмотрены ограниченно;150 уникальных B/LA частично оценены. Следующий — RES-01. Полного закрытия нет; фаза2 не начата.**
