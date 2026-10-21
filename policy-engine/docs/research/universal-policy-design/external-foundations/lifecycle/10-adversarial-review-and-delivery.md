# Крайние случаи: итоговая критика и исполнение

Проект для исполнителя, 2026-10-21. Дополняет [05 — протоколы](05-implementation-protocols.md), [06 — порядок W0–W6 и probes T01–T20](06-delivery-and-review.md), [08 — инциденты](08-incidents-and-edge-cases.md) и [09 — ресурсы](09-resource-execution-design.md). Документ не заменяет принятые SDD, не присваивает runtime acceptance и не меняет findings E02.

## 1. Предмет проверки

Root провёл связанную ревизию после шести исследовательских разрезов: recovery incidents; amplification incidents; memory/compute; metadata/invalidation; resource admission; semantic efficiency. Затем семь отдельных прямых reviewers атаковали полный проект по consistency, memory/liveness, rights, semantics, recovery, migration/free-grow и общей состоятельности. Их аргументы — анализ проекта, а не исполненные fault injections. Полные заметки и hashes сохраняются в receipt.

Ниже полный набор **15 root dispositions E01–E15** для 25 нумерованных наблюдений семи initial reviews, с объединением пересекающихся трасс. Это не 15 новых runtime defects и не перечень всех возможных атак. Все future signals **UNRUN**. `Memory/Consistency/Rights/Semantics/Recovery/Growth/Skeptic #n` — номер раздела соответствующей ignored review note из receipt.

| ID | Независимая атака и источник | Решение / bounded residual | Различающий будущий сигнал |
|---|---|---|---|
| E01 | Одновременно завершившиеся stages исчерпали reserve; native RSS не входит в estimate. Memory #1, Skeptic #4 | 09 §2: actual enforcement и terminal fan-in либо bounded terminal lane с учётом waiting state. No device-loss durability promise. | Максимальный admitted fan-in + exhaustion; убрать reserve enforcement, сохранить fields. T20. |
| E02 | Parent держит 60/100, deferred child требует 50; локальные caps соблюдены, прогресса нет. Memory #2 | 09 §2: transitive wait/resource boundary; joint supported peak либо реальный checkpoint/release до ожидания. | Parent→child→grandchild; removal yield/reservation должен выявить deadlock. T20. |
| E03 | Cancel принят до final commit, rights не менялись; поздний output всё равно видим. Memory #3 | 05 §6: operation cancel/commit order; too-late/indeterminate не terminal success. | Оба порядка cancel↔commit с unchanged rights и expired lease. T17. |
| E04 | Native CDC interval потерян до local enrollment; отдельные owner reads образуют никогда не существовавшую пару. Consistency #1–2 | 05 §4: evidenced remote-cut→local-position mapping; common-cut protocol либо qualified vector. Existing requirement усилено discriminator, не global clock. | Потерять source event до attachment; A7→A8, затем B4→B5, прочитать A7/B5. Unqualified current запрещён. T01/T05/T07/T18. |
| E05 | Revoke после check, до cache waiter/first chunk disclosure. Consistency #3, Rights #2, Skeptic #2 | 05 §5.2: operation admission linearizes с writer; bounded in-flight semantics; no global lock на network/no recall delivered bytes. | Pause после buffer/check, revoke, handoff; проверить оба порядка и continuation. T12. |
| E06 | Restore сверился до W+1; либо payload и «свежий» journal оба откатились. Rights #1, Recovery #1 | 05 §5.3: fenced switch + retained suffix; witness вне actual rollback closure и material Claim/public histories. Иначе quarantine. | Deny между replay/switch; restore всех local stores; regrant не оживляет withdrawn head. T13/T14. |
| E07 | Coalescing и независимая compaction скрыли public effect между revoke/restore; clocks перепутали порядок. Consistency #4 | 05 §4.3: минимальные effect→basis/rights/admission causal refs, allowed retention; без них history unresolved. | Reverse civil timestamps, delayed fanout, compact; удалить causal edge. T17/T18. |
| E08 | GC unlink прошёл, но mmap/native reader хранит bytes. Rights #3 | 05 §5.3: active pins входят в actual copy boundary; unlink/reclaimed placement/process-copy purge раздельны. No implied zeroization. | Удерживать view/spill page через unlink/revoke; запрет false purge, controlled drain. T13/T20. |
| E09 | Parser external ref обходит connector; opaque storage grant превращён в index/disclose grant. Rights #4–5 | 05 §5/§7: no ambient egress; отдельный admitted fetch с redirect/address policy; operation-specific grants. | Redirect/rebinding + raw-storage-only grant после parser upgrade. T11/T12/T19. |
| E10 | Provider уже раскрыл output, ответ потерян; compaction позволяет новый dispatch. Recovery #2 | 05 §5.2/§6: staged vs immediate-effect contracts; минимальный permitted no-retry binding или доказанное retirement всех replay paths. Unknown остаётся unknown. | Visible provider effect + lost receipt + dedupe expiry + restore; no blind repeat/no false isolation. T15/T16/T17. |
| E11 | Alias unchanged, resolved model/learned selection поменялись; restriction training source не видна selected refs. Semantics #1, Skeptic #1 | 09 §4/§7: exact resolved generation и материальная selection dependency; applicability оценивает rights owner, coarse invalidation если influence не отделима. | Сохранить evidence bytes/alias, изменить selector; убрать dependency и проверить fresh reader. T09/T10/T18. |
| E12 | Incremental требует всех change types; candidate ANN требует calibrated error до исследования. Semantics #2–3 | 09 §4/§7, 03 §4: exact update только supported event class; unknown recall допускает bounded candidate search без inference. | Append без rescan, затем unexpected retract; uncalibrated retrieval полезна для next query, но не доказывает отсутствие. T08/T10/T19. |
| E13 | Producer назвал материальную facet optional; migration silently dropped opaque bytes. Growth #2–3; Rights #5 | 05 §7: requiredness из frozen consumer request/rule; permitted raw/ref carry-forward либо exact loss. Strict DTO не ослаблен. | Менять только producer optional bit; old-reader→migration→new-reader с потерянной facet. T19. |
| E14 | G2 semantic release отозван, pointer на G1, G2-based claim всё ещё current. Growth #1 | 05 §7: material release withdrawal через existing generation→Claim/DV; operational rollback сам не authority event. | Fanout остановлен, fresh reader после withdrawal; history сохраняется. T07/T19. |
| E15 | Единственный control store недоступен вместе с reason-specific surface. Recovery #3, Skeptic #3 | 05 §4.3, 09 §6: accepted availability residual; ordinary unavailable если путь доступен, no cached green. Второй sovereign plane не вводится. | Убрать общий store/credential path; не считать недоставленную limitation surfaced. T07/T14/T20. |

**Root не принял более широкие выводы рецензентов.** E12 — уточнение уже существующей candidate-band границы R12/S0-K06, а не новый Pxx. Правильный scoped diagnostic no-hit не запрещается; запрещено приписывать ему полноту/отсутствие. E10 не запрещает все immediate external effects: он ограничивает конкретное обещание staged/atomic visibility и требует допустимой operation semantics. E01 не превращает ресурсный cap в научный oracle. Rights withdrawal не автоматически опровергает factual evidence или запрещает все derived models: обязательна applicability/materiality. Эти ограничения снимают governance overreach без ослабления protected границы.

P40: все dispositions отнесены к существующим классам; после расширения owner invariant новая трасса того же объявленного остатка — пример ограничения, а не бесконечный repair round. Все семь reviewers выполнили один delta-only review своих изменённых положений: исходные трассы покрыты требованиями/различающими проверками, новых противоречий в этой границе не заявлено. Root прочитал исходные и delta notes и отдельно проверил перечисленные выше overreach. Это documentary disposition ограниченного набора атак, **не доказательство полноты архитектуры и не runtime GO**.

## 2. Что должен получить исполнитель

Это уточнение уже выбранных owners и W0–W6. Не начинать новый большой framework и не делать одну задачу на каждый внешний инцидент. Первый slice остаётся один настоящий путь capture→artifact→relation→claim→change→fresh consumer. Resource contract проверяется на нём с первого implementation slice, а не добавляется после больших replay.

| Место в существующем плане | Конкретный результат | Зависимости и предел распараллеливания |
|---|---|---|
| W0: binding и backend | Actual current caller/writer/reader census; source cut/incarnation; выбранный commit domain; completion/permission predicate; enforced resource owners и bounded stages | Один canonical writer на каждый shared contract. Static map C нужно сверить с текущей веткой; он не автоматически актуален. |
| W1 + W5: bounded исполнение | Fabric bounded window, persisted refs вместо полного result list; source pressure/resume; try-reserve/defer/reconcile; nested execution использует тот же capacity owner | Runtime/Fabric binding согласовать до двух независимых правок. Capture parser можно делать параллельно claim semantics; общую admission границу не дублировать. |
| W2 + W3: семантика и change | Predicate-derived cache binding; coarse generation до fanout; сохранение event history при coalescing; gap/rebootstrap и fresh limitation | Relation owner и Claim/DV работают параллельно после фиксации cut/enrollment. Приёмка — composed reader, не два отдельных constructor PASS. |
| W4: managed copies | Spill/read lease/derivative enrollment; current rights; late-writer fence; restore quarantine и post-backup decision reconciliation | Storage/security owners; reuse выбранных протоколов. До controlled root/writer census physical GC остаётся выключенным в неподтверждённой границе. |
| W6: compatibility и эксплуатация | Второй source поддержанного класса; old/new reader; bounded cold recovery и backlog ramp; public/expert/machine limitations | После source/input/backend freeze и независимого review выполнить один измерительный wave. Real production source используется только в разрешённом локальном контуре. |

**Минимальный change packet каждого механизма:** exact source/base; один actual producer/consumer путь; schema/rule/protocol changes и affected public/generated companions; resource enforcement/recovery owner; допустимая scope/authority и remaining inputs; positive + semantic negative + removal; полный deciding output с exact runtime/backend. Не копировать tracked source и большие derived views в receipt. Failed/unavailable/skipped различаются.

## 3. Измерять границу, а не выигрыш на удобном примере

Будущая матрица остаётся частью T20 с уточнениями T01–T19. Не запускается в этой исследовательской работе.

| Нагрузка/переход | Что держать одинаковым при сравнении | Что наблюдать | Различающий провал |
|---|---|---|---|
| Много маленьких partitions | Тот же corpus/cut и output semantics | Queue/result refs, metadata edges, coordinator peak | Активный semaphore стабилен, но память растёт со всеми jobs |
| Wide/nested compressed record | Тот же logical вопрос, включая projected fields | Decoded bytes, process/runner peak RSS, native allocation, parent-buffer lifetime, parsing CPU, remaining terminal reserve | Маленький input/row count проходит, а decoded/native state без границы |
| Skew/global operator | Тот же join multiplicity/order/null/graph scope | Largest partition, output fanout, spill/write amplification | Balanced average скрывает hot key; budget stop выдан за complete |
| Generation/permission burst | Те же material events и опубликованные uses | Dirty-scope age, retries/rechecks, commit/read cut | Coalescing стирает временный запрет или очищает g+1 по результату g |
| Slow/failed provider | Тот же logical operation и effect identity | First-attempt age, quota/cooldown, chain attempts, held resources | Layered retries или timeout дублируют effect/освобождают живую работу |
| Restore + expired replay | Backup root, post-backup decisions, actual retained suffix | Rebuild state, common dependency, fresh reader, backlog | Старый cache/offset возвращает green после deletion/restore |
| Semantic optimization | Тот же selected question/population/method | Error/coverage и threshold margin вместе с CPU/RAM | ANN no-hit, arbitrary epsilon или missing-as-zero меняют вывод |
| Mixed versions + resource pressure | Required meaning, permission и supported feature set | New/old roots, reader coverage, recovery state | Rollback возвращает semantic bypass или публикацию только первых pages |

Команда исполнителя заранее устанавливает measured wall-time/space limits и локальный compute slot. Сначала frozen source и review, затем wave. Product execution самого атласа не требуется. Для exact оптимизации сравнивать с owner reference на том же cut; где нужен независимый substantive oracle — он относится к проверяемому semantic predicate, а не ко всем hash/parse операциям подряд (S0-K14).

## 4. Архитектурная граница и остатки

Этот пакет не выбирает новый storage/query/workflow engine, новый global status lattice, universal evidence DTO или новый sovereign owner. Engine-specific улучшения допустимы через существующие adapter seams после измерения. Нет основания переносить весь payload в distributed cluster, если нужную границу закрывают partitioning, ограничение очереди и согласованное native execution.

Настоящие внешние inputs остаются внешними: source snapshot/change guarantees и доступ; competent rights/applicability/law; source custody/currentness; научные допущения и population; provider lookup/idempotency/quotas. Исполнитель обязан проверить доступные local paths и разумные exact/conditional альтернативы, но не может создать эти факты декларацией. Unavailable input ограничивает конкретный use, не весь исследовательский candidate band.

Actual SDD directory этой работой не меняется. Предыдущий [C03 proposal](../sdd-proposals/lifecycle-c03-20261021.md) остаётся на согласовании. Resource planning, bounded queues, recovery, cache scope и operation-specific gates развивают уже принятые custody/authority/time правила. Если реализация требует materially нового semantic promise, общего wire contract или sovereign ownership, сначала представить отдельный узкий proposal вне authoritative directory; не считать любое engineering поле новой архитектурной развилкой.

Все performance numbers и behavioral probes остаются **UNRUN**. Документарные проверки подтверждают файлы, ссылки и источник анализа; они не подтверждают runtime свойства, throughput, OOM safety, RPO/RTO или formal closure.

Pattern pass: P01/P02/P27/P31 — complete owner chain; P04/P05/P09 — honest authority/currentness; P07/P08 — versions/cuts/time; P10/P14/P25 — meaning/selection; P13 — proportional cost; P29/P32/P35/P37/P38/P40 — actual property and bounded review. Не вводится новый Pxx или продуктовый enum.
