# CMP-02 — уникальный slot producer, честный WARN и порядок по occurrence
## C43 · 31 октября 2026 года

**Исходные IDs:** B45, B46. **Порядок:** 43/127. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит.

## Решение

**Механика обеих исходных находок исправлена в текущих owners:** compiler вызывает shared chain-level checker по конкретным endpoints; STRICT отвергает duplicate producer. Semantic validator проверяет каждую node occurrence, а не последний индекс общего FQN.

**WARN намеренно остаётся ограниченным diagnostic contour:** перестановка UUID меняет выбранное значение 20↔10, но collision warning и validation mode не исчезают ни в result, ни после checkpoint fresh readback/resume. Это не silent merge и не полномочие на научный вывод. Новых product defects в данном scope не установлено. **19 bounded MATCH / 0 ERROR; native tests BLOCKED.**

## 1. Матрица исходных IDs

| ID | Реально подтверждено | Остаток |
|---|---|---|
| B45 | Actual occurrence checker; STRICT отказ; distinct slots/explicit merge; warning/result/checkpoint continuity и removal controls | G01 native chain; G02 корректная роль WARN у downstream consumer |
| B46 | Early estimate не теряется из-за позднего повторения; каждое раннее sensitivity нарушение имеет node_id/index; STRICT/WARN различены | G01 native tests; G03 научные пределы tag heuristics |

[Полная карточка](../05_Источники/CMP-02_исходные_строки.txt), строки 5325–5427. Исходное требование — не допустить **молчаливый** last-wins; оно не требует уничтожать полезные явно ограниченные candidate результаты.

## 2. B45 — collision проверяется на уровне actual composition

`MethodComposer.validate` вызывает существующий `SlotLinker.validate_chain` с mapping node_id→signature и полным набором edges. Checker сверяет occurrence binding с owning edge, повтор concrete target slot и joint completeness. STRICT либо strict linker policy отказывает; tolerant profile сохраняет limitation в warnings. [S01:650–706](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/composer.py#L650-L706) [S02:452–535](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/linker.py#L452-L535)

P01 actual add/connect/build отвергает два scalar producers в STRICT. P02 strict linker policy отказывает и при WARN compiler mode. P18 altered binding source_node_id не совпадает с edge и обнаруживается checker. P19 pair construction может оставаться partial, но final strict joint validation отвергает незаполненный right input.

Это не вручную нарисованный graph: exact MethodComposer, typed Unit/SlotSpec/MethodSignature, explicit SlotLinker и scalar strict-shape checker реально исполняются. Registry и dispatcher — явные fixtures; neutral name-semantic seam не доказывает смысл всех slot names. [S04:393–763](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/base.py#L393-L763) [S05:250–387](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/types/checker.py#L250-L387)

## 3. WARN не скрывает остаточную неоднозначность

P03/P04 строят одинаковую содержательную пару producers 10 и 20, меняя только закреплённые UUID. Sequential и async продолжают выбирать последнее binding: outcome **20 или 10**. Но в каждом result присутствует `[slot] … connected multiple times`, validation_context имеет `mode=warn`. P05 semantic OFF также не стирает slot collision warning.

Это **не определённая merge semantics**. Нельзя называть такой численный результат UUID-invariant или однозначным. Вместе с тем это намеренный текущий tolerant profile, закреплённый tests; он не признан product defect только потому, что допускает candidate execution с явной оговоркой. Путь до publication/authority consumer здесь не проверялся, поэтому утверждения о фактическом ошибочном повышении результата нет.

P07 снятие warnings с compiled chain не делает её чистой: existing replay заново вычисляет diagnostics и отказывает до dispatch. Обе local execution поверхности возвращают warnings/validation_context, не только промежуточный plan. [S01:920–979](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/composer.py#L920-L979) [S07:984–995](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/chain_executor.py#L984-L995) [S08:270–286](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/async_chain_executor.py#L270-L286)

**Контроль P06:** два разных входа left/right и явный Merge складывают 10 + 20, downstream умножает на 2. Все четыре sequential/async × UUID permutation запуска дают **60**, без collision warnings. Actual IO materialization/dematerialization и identity binding adapters исполняются; арифметический oracle независим от UUID. Это synthetic алгоритмический контроль, не empirical policy evidence. [S06:34–129](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/io.py#L34-L129)

## 4. Диагностика доживает до persisted consumer

Checkpoint owner сохраняет validation_context и composition_warnings, а execution digest включает текущие bindings, effective predecessors, input/parameters/seed и diagnostics. При resume он сверяет live compiler replay, persisted context/warnings и execution identity до использования completed prefix. [S09:372–444](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/checkpointing.py#L372-L444) [S09:530–579](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/checkpointing.py#L530-L579) [S09:613–730](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/backends/checkpointing.py#L613-L730)

**P08:** actual checkpoint executor завершает три узла, actual snapshot/save пишет JSON через реальные lock/fsync/atomic rename в audit directory. Fresh `ChainCheckpoint.load` и новый executor восстанавливают **3 node results, 0 новых dispatches**, сохраняют collision warning и WARN mode. Protocol result/timing/reproducibility classes — fixtures; это не native backend provenance или Core CAS.

P09 меняет persisted diagnostics_digest; P10 удаляет warning list; P11 удаляет validation context; P12 помечает completed slot-output history неполной. Все четыре случая дают typed refusal до dispatch. Ограничение не исчезает при сохранении/повторном чтении и не превращается в reusable authoritative result.

Этот witness дополняет предыдущую границу C42: existing persisted checkpoint действительно связывает effective plan identity и diagnostics. Он всё ещё требует supplied live compiled plan и **не доказывает standalone ChainArtifact→fresh compiler reconstruction**. Новая параллельная архитектура не нужна.

## 5. B46 — проверяется конкретный узел, не последний FQN

Validator хранит ordered `(node_id,fqn,tags)` и для каждого dependent ищет prerequisite с меньшим index. Diagnostic содержит target_node_id и target_index. Family/variant/data_modalities — rough tag proxies, а не полный методологический контракт. [S03:233–314](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/semantic_validator.py#L233-L314)

В отличие от части repository tests с минимальным chain protocol, наши probes проходят actual composer:

- **P13:** estimate₁ → sensitivity → estimate₂ проходит WARN и STRICT, раннее основание не теряется.
- **P14:** sensitivity₁ → estimate → sensitivity₂ сохраняет ровно нарушение index 0; WARN выдаёт конкретный target, STRICT отказывает.
- **P15:** sensitivity₁ → sensitivity₂ → estimate → sensitivity₃ даёт два diagnostics для indices 0/1, не для позднего узла.
- **P16:** occurrence одновременно с estimate/sensitivity tags не считается собственной предшествующей prerequisite.
- **P17:** нейтральные неизвестные tags не запускают rule. Чистый STRICT report здесь **не доказательство научной допустимости**.

Правильная индексация не делает утверждения вроде общих запретов simulation→causal универсальными законами. Для конкретной задачи нужны обоснованные assumptions/данные/контракты; LLM может предложить схему, но compilation warning checker не заменяет её проверку. [S03:105–151](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/components/semantic_validator.py#L105-L151)

## 6. Tests и сохранённые ограничения

Полный `test_cmp_02.py` прочитан, 317 строк. B45 cases используют actual registry/composer; checkpoint case проверяет fresh readback и stripping diagnostics; B46 focused cases намеренно используют minimal protocol, а не native executor. Эти уровни не смешаны. Native команда остановилась до collection: `No module named pytest`, exit 1. Первый bounded запуск дал 19 MATCH / 0 ERROR; исходники и зависимости не менялись.

Сохранить concrete checker, occurrence diagnostics, explicit merge, честный tolerant contour, actual persisted warning continuity и existing replay. Native qualification и authoritative downstream use остаются отдельными остатками; не нужно блокировать всякую кандидатную работу или вводить новую систему полномочий.

[Диагностика](../04_Проверки/C43_CMP02/bounded_diagnostics.json) · [Команды](../04_Проверки/C43_CMP02/commands.json) · [Native границы](../04_Проверки/C43_CMP02/native_verification.json) · [Источники](../05_Источники/C43_источники.json) · [Остатки](../01_Реестры/C43_остатки.json).

**43/127 пакетов рассмотрены ограниченно; 103 уникальных B/LA частично оценены. Следующий — CMP-03. Полного закрытия нет.**
