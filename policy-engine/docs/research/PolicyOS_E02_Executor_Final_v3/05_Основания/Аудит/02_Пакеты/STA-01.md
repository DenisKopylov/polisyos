# STA-01 — изоляция ветвей и точные эффекты replay
## C61 · 1 ноября 2026 года

**Порядок:** 61/127, LANE-06. **Исходные ID:** B57, B58, B59. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Свежий проход после внешнего сохранения C60.

## Решение

Основные repairs содержательны: actual journal хранит намерения, в том числе запись прежнего значения; replay применяет их к текущей основе, а не сравнивает старый post-state с нынешним. Delete, null и no-write различены. Объявленное mutable subtree изолируется глубоко, unrelated область не требуется безусловно копировать целиком.

**8 bounded MATCH; 29 unchanged test bodies /34 cases PASS изолированно.** Подтверждён **C61-R01**: whole-root `set` может удалить protected index keys, хотя explicit `delete` отказан. Native CAS/restart/process chain остаётся UNRUN. MATCH отрицательного контроля не означает product PASS.

## 1. Матрица исходных ID

| ID | Требование | Свежая проверка | Остаток |
|---|---|---|---|
| B57 | Replay только actual effects, same-value assignment и unrelated preservation; snapshot не patch | P01/P03 current unrelated=new,y9→4; actual canonical journal→executor helper; P05 proof/tamper; P08 bool/int | G01 native store/restart; G02 внешние эффекты |
| B58 | Delete≠null≠no-write, атомарные конфликты и защищённые индексы | P01 все merge regressions; P07 late failure сохраняет base; P06 explicit delete vs root replacement | R01 protected membership; G01 routes |
| B59 | Deep declared subtree, сосед/основа не видят failed branch | P02 nested dict/list/model и unchanged unrelated identity; P04 DAG alias/sibling isolation; depth/cycle controls | G01 native failure rollback; G02 finite profile |

Полная карточка7249–7365 прочитана. Предложенного `test_sta_01.py` в checkout не найдено; проверены фактические existing owners/tests, а не наличие имени файла.

## 2. Intent journal устраняет исходный snapshot replay

Actual tracked dict/list/model записывает concrete operation, path, value и target presence/kind. Top-level setters фиксируют даже присваивание равного значения. Merge выбирает journal operations в declared subtree, deduplicates overlapping declarations, сохраняет ordinal order и сначала разрешает межветочные конфликты. Он не обязан превращать отсутствие изменения байтов в отсутствие намерения. [S01:103–174](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/state_branching.py#L103-L174) [S01:864–1227](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/state_branching.py#L864-L1227) [S02:178–327](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/state_merge.py#L178-L327)

**P01:** все21 test body /25cases из actual merge файла исполнены. Среди них: unrelated update, y=4 поверх текущего9; delete/null/no-write; child-set→parent-delete и parent-set→child-delete; parent/child conflict; один append при overlapping declarations; typed refusal для missing/wrong-kind/index targets; top-level ref assignment. Это реальные branch/merge/state owners с минимальным test runner, не переписанная модель алгоритма.

**P03:** actual enforced producer на old state с y=4 явно записывает4. Operations проходят настоящий Core canonical bytes→decode→StateMutation DTO→journal. Actual `_merge_cached_outcome_state` получает current state с y=9,unrelated=new и уже отсутствующим старым полем. Итог: **y=4,unrelated=new**, удалённое чужим шагом поле не воскресает. Старый post-state присутствует в outcome, но deciding effect берётся из журнала. [S04:527–542](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/executor.py#L527-L542)

**P07:** первая операция меняет a, вторая pop(1) несовместима с нынешним пустым списком. Merge выдаёт StateReplayIncompatible; caller base остаётся a=9,items=[]. Частично применённое внутреннее состояние не возвращается как commit. Native executor по source при этом evicts/bypasses cache и переисполняет node, а не сообщает hit success. Полный executor test этого поведения прочитан, но UNRUN. [S02:142–175](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/state_merge.py#L142-L175) [S04:1513–1550](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/executor.py#L1513-L1550) [S12:367–407](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/orchestration/engine/test_engine_executor_idempotency.py#L367-L407)

## 3. Carrier и reader согласованы, но proof fixture не CAS

Current entry schema2.0,mutation version1.2,replay epoch2.1 связывают embedded outcome, ordered journal и manifest schema/producer proof. Reader проверяет custody, run/key/scope, complete current operations и canonical равенство живого журнала сохранённому. Historical entry без достаточного replay contract становится miss; predecessor v1 с доказанным scalar intent не blanket запрещён. [S03:51–235](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py#L51-L235) [S03:565–766](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py#L565-L766)

**P05:** actual NodeCacheEntry/JournalProof и `_replay_proof_valid` проходят canonical wire roundtrip; changed operation value, snapshot без journal contract, unknown epoch и incomplete mutation fields отказаны. **P08:** True и1 различаются actual canonical operation bytes, несмотря на Python True==1. Manifest здесь — явная fixture для проверки proof math/contract, **не настоящий store manifest/custody**.

Source-only writer записывает entry и после verification публикует cache index; cache get восстанавливает journal на outcome state. Checkpoint materialization, напротив, восстанавливает полное состояние своей цепочки; resumed runner получает state и отдельные cache seed refs. Snapshot не переименован в универсальный patch. [S03:770–864](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py#L770-L864) [S08:2237–2291](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py#L2237-L2291) [S08:2615–2685](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py#L2615-L2685)

## 4. B59: изолированное subtree и предел поддержанного графа

Предки пути копируются поверхностно, на объявленной границе выполняется глубокое копирование с общим memo. Tracker сохраняет aliases и вычисляет live paths, а enforced producer не может молча расширить write scope. Не требуется `deepcopy` всего ExperimentState на каждый node. [S01:491–617](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/state_branching.py#L491-L617) [S01:1680–1761](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/state_branching.py#L1680-L1761)

**P02:**8 selected branch bodies /9cases подтверждают nested list elements, typed Pydantic container, top-level ref journal, snapshot copy, shared unrelated identity в необязательном narrow branch profile, cycle refusal и canonical depth124 accepted/125 refused. Это не весь1376-line model/hook test corpus.

**P04:** два поля declared config разделяют один список словарей. Actual enforced branch сохраняет alias внутри своей копии; изменение value1→2 не видно ни base, ни sibling. Затем внешняя fixture выбрасывает exception без commit: обе независимые основы остаются1. Это bounded rollback prerequisite, **не выполнение native failed-node WorkflowExecutor**.

Actual admission ограничен callback-free finite JSON/ordinary typed model graph. Цикл явно отказывается; он не превращается в потерянный alias или бесконечное копирование. Такой честный профиль лучше ложного обещания поддержки произвольного Python object graph. [S01:1802–1898](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/state_branching.py#L1802-L1898)

## 5. C61-R01 — protected deletion проверяется по имени операции, не результату

**Средняя серьёзность; высокая уверенность в bounded actual declared branch→merge.** Merge запрещает delete/pop/remove/clear и delete-index/slice под inputs/artifacts_index/reports_index. Но `set` целого корня обходит этот список, а setter допускается declared scope. Отдельный StateMutationGuard определяет потерю ключей по before/after membership и такое изменение отвергает. [S02:472–526](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/state_merge.py#L472-L526) [S05:47–78](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/guards.py#L47-L78) [S05:107–121](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/guards.py#L107-L121)

**P06:** для каждого из трёх roots создан настоящий ExperimentState с typed ArtifactRef и `enforce_write_scope=True` branch. `del root['evidence']` при merge получает «deletion forbidden». Эквивалентное по потере membership `root={}` создаёт operation=`set`; merge возвращает пустой индекс. Actual `StateMutationGuard.post_check` для этого же результата выдаёт «state index keys removed».

Это конкретная несогласованность invariant между существующими owners, **не удаление CAS bytes**, не доказанный production incident и не security exploit. Полный engine route не выполнен; нельзя делать вывод о каждом native cache-hit. Тем не менее declaring root writable не должно отменять явно установленный запрет исчезновения evidence keys только из-за другого spelling операции.

Минимальное направление: согласовать before/after protected membership с existing staged operation/replay boundary, включая whole-root replacement. Сохранить разрешённое обновление ref/добавление key, params deletion и реальные versioned revocation semantics; не запрещать всю полезную запись индекса и не создавать второй patch service. Проверить cold, parallel и cached routes одним согласованным contract.

## 6. Native и содержательная capability-граница

**C61-G01:** native pytest отсутствует; public import underPython3.12.14 останавливается в Core store на Python3.14 exception syntax. Pydantic2.13.4 также вне pinned<2.13. В isolated run использованы actual modules с восемью package initializer shells; boot, CAS get/put, fresh reader, restart и process wire не выдаются за пройденные. Existing native current-state/retry/failed-node tests и worker branch-before-execute/completed-before-wire flow прочитаны. [S09:239–330](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/runner/_activity_worker.py#L239-L330)

**C61-G02:** state intent replay не доказывает идемпотентность списания средств, event append и внешнего действия. Им нужны их existing operation identities/admission; нельзя переигрывать их как обычные set. Нет измеренного serialization/RAM speedup, общего Python sandbox или empirical policy authority. Содержательный результат здесь — возможность безопасно сохранить и переиспользовать полезную исследовательскую ветвь в указанном finite profile, а не новый deterministic model inventor.

Сохранить полезный journal/current-base/immutable-source design, typed targets, alias-aware isolation и explicit unsupported refusal. Исправить R01 через existing owners; закрыть native qualification подходящими existing integration tests, без новой paperwork architecture.

Первый bounded run exit0. Repo clean; source/test/config/dependency edits, installs и services отсутствуют.

[Диагностика](../04_Проверки/C61_STA01/bounded_diagnostics.json) · [Команды](../04_Проверки/C61_STA01/commands.json) · [Native-границы](../04_Проверки/C61_STA01/native_verification.json) · [Источники](../05_Источники/C61_источники.json) · [Остатки](../01_Реестры/C61_остатки.json).

**61/127 пакетов рассмотрены ограниченно; 143 уникальных B/LA частично оценены. Следующий — STA-02. Полного закрытия нет.**
