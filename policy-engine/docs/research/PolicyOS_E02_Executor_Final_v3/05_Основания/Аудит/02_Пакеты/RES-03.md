# RES-03 — частичный результат остаётся результатом, а отказ остаётся отказом
## C67 · 1 ноября 2026 года

**Порядок:** 67/127, LANE-06. **Исходный ID:** B13. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Свежая проверка после внешнего сохранения C66; утраченный прежний C67 не переаттестован.

## Решение

**9 bounded MATCH, включая четыре изолированно исполненных existing test bodies. Новый подтверждённый продуктовый R не установлен.** Исправление async-chain действительно сохраняет успешного соседа и предыдущие уровни в исключении, не превращая цепь в успешную. Есть содержательный recursive partial owner, строгий графовый контроль и consumers для отображения и нормативного отказа.

Однако завершённый соседний leaf и завершённая симуляция внутри ещё не законченного leaf — разные границы. Полная гарантия B13 после позднего отказа того же leaf, native CAS/readback, повтор и отзыв зависимой authority пока не квалифицированы. **Полного закрытия нет.**

## 1. Исходная матрица

| Часть B13 | Фактический результат | Остаток |
|---|---|---|
| A success / B fail в async-chain | P01–P03: A и предыдущий уровень доступны, exact error сохранена, dependent не запускается | G01: штатный dispatcher и полный consumer |
| Численный producer перед отказом | P05: actual async owner сохраняет NumPy least-squares результат и scope в исключении | Это synthetic producer, не native PolicyOS N5 или CAS |
| Завершённый recursive leaf перед отказом соседа | Typed V3 producer и existing real-leaf test найдены; actual predicates/projection/guard проходят P07–P09 | G01: native producer → CAS → HTTP и invalidation/reuse |
| Поздний этап того же leaf падает после N5 | P06 и source boundary показывают, что общий cycle record возникает только после engine | G02: точный native сценарий и public partial readback |

Полная карточка прочитана. Исходное ограничение «не утверждать, что всё теряется» сохранено: N4/source/CAS и завершённые leaf records не объявлены отсутствующими.

## 2. Async-chain: merge раньше terminal error

`_execute_level` собирает успехи и ошибки раздельно. `execute` сначала выполняет `_merge_level_results`, затем создаёт `ChainExecutionResult` из всех завершённых узлов и поднимает `AsyncChainExecutionError`, содержащую этот partial, исходные ошибки, индекс уровня и blocked future nodes. Failed node не включается в node_results. [S01:206–259](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/async_chain_executor.py#L206-L259) [S01:295–376](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/async_chain_executor.py#L295-L376)

**P01–P04:** четыре существующих test bodies выполнены unchanged, но с явно описанными registry/dispatcher/metadata/raises fixtures. A=7, scope и artifact-ref строка остаются читаемыми; ошибка B — именно ValueError с исходным текстом. Предыдущий уровень сохранён, dependent C не вызван и указан blocked. All-success control возвращает четыре результата. Строка `sha256:left` в тесте не является проверенным CAS-артефактом. [S02:84–229](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_res_03.py#L84-L229)

**P05:** отдельный producer действительно вычислил least-squares коэффициенты для синтетических `y=2+3x`: приблизительно 2 и 3. Следующий узел выбросил заранее созданный RuntimeError. Actual async exception сохранила тот же объект ошибки, оба числа и scope с явной отметкой synthetic / authority none. Вычисленный результат читается из `partial_result`; CAS не записывался. Это проверяет передачу содержимого, а не научную состоятельность мировой модели.

Сохраняются настоящие compiler/plan admission и IO definitions; не подставлена произвольная структура вместо compiled chain. Но reproducibility contract, штатный MethodResult и native dispatcher в этом опыте не квалифицированы. Shallow state merge также не является общей системой dependency invalidation: зависимость authority проверяется её отдельным owner.

## 3. Recursive partial — не пустой статусный DTO

Actual router принимает только законченный canonical cycle run с правильным problem binding и candidate validation. При отказе следующего leaf после завершённого sibling создаётся `_RecursiveSiblingFailureError`; верхний owner строит V3. Если ещё нет завершённого подходящего sibling, исходная leaf error пробрасывается. Builder сохраняет completed nodes, ровно один failed branch и остальные pending; root terminal равен `None`. [S04:3573–3672](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py#L3573-L3672) [S04:2406–2475](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py#L2406-L2475) [S04:3916–3931](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py#L3916-L3931)

V3 не разрешает «сохранить красивый статус и убрать producer». Guard пересчитывает полный denominator графа, topology, depth/budget, сопоставляет leaf terminal с его cycle owner и проверяет completed-before / pending-after вокруг ветви отказа. Он также проверяет origin ошибки внутри failed branch и content hash. [S04:2046–2150](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py#L2046-L2150) [S04:2312–2403](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py#L2312-L2403)

**P07:** actual graph/V3 predicate bodies приняли fixture root pending / A completed / B failed / C pending. Пять отрицательных controls отказали: удаление A, повышение C до completed, подмена origin на уже завершённый A, root terminal success и изменённый hash. DTO, hash и terminal-owner в этом bounded вызове — fixtures. Поэтому здесь нет утверждения о native Pydantic V3 roundtrip или настоящем GY wire.

Полностью прочитан существующий `test_real_leaf_result_survives_later_independent_sibling_failure`: он использует owner-bound N5 fixture store, default recursive controller, controlled N4 port и tenant scope; повторно читает сохранённую simulation с expected WMR/atoms/outcomes, проверяет точную ошибку, отсутствие promotion receipts, nested completed sibling и отрицательные controls. **Этот native test не исполнен.** Его наличие — содержательный coverage intent, не fresh PASS. [S05:1–336](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/runtime/quality/test_recursive_generation_cycle.py#L1-L336)

## 4. Есть consumers; partial не становится нормативным успехом

Compiled owner сохраняет recursive payload и отличает failed-partial schema от budget stop и обычного run, включая более новые schema extensions. Simulate-only job writer сохраняет compiled artifact и завершает job attempt. Его `state=completed` само по себе не означает, что recursive traversal завершился успехом или появилась нормативная authority. [S07:1139–1188](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py#L1139-L1188) [S07:2829–2861](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py#L2829-L2861) [S08:971–1056](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/control/job_nl_execution.py#L971-L1056)

API checkpoint projection выводит отдельно completed refs, pending frontier, leaf terminal kinds и exact branch failure. **P08:** actual projection сохранила A / root,C / B и точный текст ошибки; обычный непарциальный объект дал `None`. Публичный receiver перед этим проверяет manifest, tenant/cell, bytes/hash, selected profile и compiled model. Эти проверки прочитаны, но в P08 не исполнены — DTO projection не заменяет HTTP/CAS admission. [S06:360–422](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/routes/runs.py#L360-L422) [S06:1326–1470](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/routes/runs.py#L1326-L1470)

**P09:** actual `_normative_generation_sources` отверг V3 с `p20_normative_partial_compiled_run` ещё до публикации leaf sources. Artifact read/model validation здесь fixtures; сам early normative guard настоящий. Полезный candidate result не повышен до нормативной подписи. [S07:592–646](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py#L592-L646)

## 5. Что остаётся проверить — без тезиса «всё потеряно»

**C67-G01.** Native owner-bound N5 → CAS → compiled partial → scoped public readback, после sibling failure, ещё не исполнен. Сохранить existing real-leaf test и дополнить общим LANE-06 integration сценарием с actual selected profiles, повтором и изменением общего основания. Наличие ref не доказывает bytes retrieval, актуальность scope или право reuse. При invalidation зависимая authority должна отозваться; независимый candidate artifact не обязан исчезнуть.

**C67-G02.** Same-leaf граница остаётся отдельной. `SimpleLoopEngine.run_async` не прикладывает state к исключению. `_run_cycle` получает cycle и делает свой N7 checkpoint только после успешного возврата engine. Joint-value implementation сначала получает simulation, затем вызывает value receiver; recursive sibling partial сохраняет только законченные cycle runs. [S03:45–56](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/workflows/engine_simple.py#L45-L56) [S09:9472–9526](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L9472-L9526) [S09:13562–13689](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L13562-L13689)

**P06** подтверждает узкую семантику minimal engine: промежуточные simulation/scope достигли следующего callable, ошибка вышла без `partial_result`, исходный initial dict остался пуст. Это **не** native N5 и **не** доказательство отсутствия самостоятельных CAS-записей. Нужен различающий сценарий после настоящего N5 с отказом value/revision того же leaf и чтением результата через существующий reader. При необходимости расширять existing source/checkpoint boundary, а не строить второй журнал или второй scheduler.

## 6. Исполнение и пределы

- Bounded run: exit 0, **9 MATCH**, из них четыре unchanged existing bodies с fixtures.
- Native pytest: exit 1, модуль pytest отсутствует; ни один native body не выполнен.
- Public import: exit 1, Python 3.12 не разбирает Python 3.14 syntax в `ir/analytics/uncertainty.py:287`. Repo требует Python 3.14; установленный Pydantic 2.13.4 также вне закреплённого диапазона. Это не продуктовые R. [S14:278–292](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/uncertainty.py#L278-L292) [S15:1–30](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/pyproject.toml#L1-L30)
- Исходные файлы сверены с pinned Git blobs, checkout чист. Ничего не установлено и не изменено в репозитории; внешние сервисы не запускались.
- Empirical validity, native durability, стоимость повторов и весь public lifecycle не измерены. LLM может предлагать следующий исследовательский шаг, но synthetic partial не становится от этого grounded evidence.

[Диагностика](../04_Проверки/C67_RES03/bounded_diagnostics.json) · [Команды](../04_Проверки/C67_RES03/commands.json) · [Границы](../04_Проверки/C67_RES03/native_verification.json) · [Источники](../05_Источники/C67_источники.json) · [Остатки](../01_Реестры/C67_остатки.json).

**67/127 пакетов рассмотрены ограниченно. Следующий — RUN-01. Полного закрытия нет; фаза 2 не начата.**
