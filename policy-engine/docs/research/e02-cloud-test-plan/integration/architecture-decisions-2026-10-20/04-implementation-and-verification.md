# Исполнение решений: зависимости, ресурсы, acceptance

Это задание исполнителю после архитектурного выбора; **никакие перечисленные проверки в этом исследовании не запускались**. Авторский code остаётся непринятым. Закрытие ID проводится отдельно по original criterion, а не автоматически по наличию этих contracts.

## Что начать без нового архитектурного ожидания

Сначала reconcile текущий coding source с snapshot `11ff2421…`, прочитать актуальные AGENTS/HANDOFF, D01–D08, [финальные решения](06-final-decisions-and-solo-review.md) и три AD. Сохранить source/tree/ref и собственные изменения. Новое состояние не исправлять reset/rebase/переключением ветки. Использовать текущий admitted checkout, а не размножать окружения. Не копировать этот старый source поверх более нового. Предложенные новые schema versions относятся к исследованному baseline; при уже занятой версии выбрать следующую через тот же canonical inventory, не менять смысл опубликованной версии.

| Wave | Исполняемая работа | Выход и условие перехода |
|---|---|---|
| 0 — shared foundation | Correct Core decoder; exact selected profiles; сохранить profile EnvironmentManifest; починить retry-view composition; выбрать existing guarded run-record extension и schema inventory | На малом exact-source slice подтверждён реальный codec/source путь. Ни один дефект не объявлен inherited без P41 |
| 1a — input | Один strict observational_input; lightweight method/defaults/runtime pins до acceptance; requested/content-admitted intent; HTE target/normalizer | Typed producer/reader + lineage; method не меняется при ожидании. B основной; A explicit compatibility |
| 1b — compute | AD02 lazy/ref submission, finite FIFO/backpressure/cancellable handle, serial folds; prepare→dispatch→persist→refs | Один physical slot owner; late callbacks, completed outputs и exception frames не обходят memory boundary |
| 1c — metric compile | AD01 binding schema + compiler law/adapter + graph validator; selected registry semantics | One-way CAS DAG, исполнение law против actual input roles, никакого имени как oracle |
| 2 — compose owners | Graph capture + bundle; atomic owned attempt tuple; intent/lease/result linkage; admission worker→persisted typed PolicyEvaluationVector 1.2 projection + guarded association | Current/historical/partial/verification-missing различаются; caller-created run/projection не принимается |
| 3 — consumers/surface | Scientist objective/L3/L4; bounded cold RunIndex/GET; DTO/schema/OpenAPI/clients/browser companions | Настоящий persisted consumer; ни model replay, ни arrays/law recomputation на GET |
| 4 — focused verification | Все source и contract reviews до freeze; matched removals; complete B56 roster; ordinary HTTP + fresh reader | Полные deciding outputs, включая failures/skips, а не пересекающиеся sums PASS |
| 5 — final integration | Explicit source/input/backend freeze, independent review и affected defining properties; затем один общий дорогой replay | Integrated result отдельно от production-dependent closeout и formal finding adjudication |

1a/1b/1c можно проектировать параллельно, но общий Runtime payload, schema registry и run-record имеют **одного назначенного writer**; изменения согласуются через маленькие typed interface diffs. Не выдавать трём исполнителям один общий файл. Runtime/Foundry boundaries и copied params/ref structures должны быть согласованы до композиционного теста. Нагрузка общих scratch/DuckDB/native memory сериализуется; независимые статические reviews не требуют machine slots. Здесь намеренно нет нового деления A–F.

Compiled method metrics (AD01) и HTE causal input (AD03) — разные реальные routes, переиспользующие identity/commit/units/admission. Не навязывать каждому causal HTTP run SimulationResult, если его canonical owner выдаёт другой typed result; run-record extension связывает правильный тип результата и intent. Conversely, HTTP positive не доказывает ProgramGraph metric capability. Общие носители не делают две capabilities одной.

## Acceptance matrix: property, независимый oracle, removal

| Property | Минимальный реальный positive | Oracle / decisive negative |
|---|---|---|
| Graph method → выбранный metric | Compiled graph, настоящий dispatcher, output CAS, owned selection, fresh admission и objective consumer | Аналитически проверяемый маленький fixture + independent reader; правильно rehashed forged bundle/run label не проходит controlled commit |
| Metric meaning / unit | Реальный law вычисляет из captured typed input/output и выбранного semantic definition | Same-shape different population/time; weights→employment; USD→UAH; level→delta. Unit string unchanged не спасает |
| Complete graph run | Все planned/actual occurrences/outcomes, repeated feedback IDs, required slots | Duplicate node/slot, скрытый failed/skipped occurrence, dropped mandatory output; partial sibling success сохраняется с правильным status |
| Retry/current selection | Два competing attempt, поздний callback старого | Независимая история CAS/fence; atomic tuple, stale pointer update запрещён; partial refs pair не читается как current |
| Shared cap | Complete declared model/fold/repeat/seed roster на cap 1/2 через common Runtime owner | Execution-boundary observer + prefix history checker; owner removal при достаточном числе callers действительно превышает cap |
| Queue/cancel/resource | Ref-only waiting, parse внутри slot, queued cancellation, running timeout+retry | Убрать ранний bridge при сохранённых cap markers; observe allocation/start outside boundary, double-release/stale publication negatives |
| HTTP selection | Ordinary authenticated POST→real worker→input owner→CAS→fresh GET | Убрать request→intent/state mapping при сохранённом DTO; positive обязан сломаться. Не internal enqueue witness |
| Versioned HTE input | B real target/producer; A explicit normalization отдельным тестом | Missing discriminator при сохранённом envelope kind; wrong target/profile; raw fallback запрещён |
| Source snapshot/privacy | Один guarded selected view по всей цепочке | Same payload/different profile; backing alias replacement; access revoke; derived private data не становится public по default |
| Migration | Old omit, new strict selection, historical artifacts и state resume | Present-null vs absent; edge stripping старым writer; method/default/registry drift без нового selection; latest substitution запрещена |
| Prequeue method identity | POST принят, затем registry/defaults/build изменились до dequeue | Исполнение использует pinned поддерживаемую boundary либо typed refusal; результат под новыми defaults без нового intent запрещён |
| Persisted verification | Fresh worker проверяет raw source и сохраняет typed projection; fresh process её читает | Rehashed forged projection без owned association отвергается; old-source association не годится после retry; cold GET не вызывает heavy paths |
| Completed-result/callback memory | Worker возвращает refs после persistence, failure handles не держат input frames | Slow persistence, failed serialization, late callback и накопление completed futures не выносят arrays/compute из admitted boundary |

Independent oracle здесь означает второй способ установить **конкретное** свойство. Ручная арифметика может подтвердить reduction на fixture, но не causal identification в мире. Same-code deterministic replay подтверждает согласованность, не научную независимость. Permit trace checker проверяет trace invariant, а execution observer нужен для связи с реальной работой. Защищённая owner transaction подтверждает accepted origin, не истинность observations.

Численные tolerance выбирать до результатов по backend/dtype/error budget; exact refs/schema/profile/status не сравниваются «примерно». Для stochastic replay заранее задать RNG/seed plan, target statistic/equivalence margin/error rate. Overlapping CI не является доказательством equivalence. Пересечение decision boundary сохраняет `near_binding`/existing review semantics.

## P37 admission predicates и P05 purpose

Классификация ниже задаёт **требуемый способ установления**, не объявляет его исполненным сейчас. До реального verifier receipt runtime property остаётся `not_established`. При admission каждый load-bearing predicate получает одну существующую P37 label; label, evidence ref, verifier/rule version и checked context фиксируются с projection. Новая metadata запись сама не делает predicate доказанным.

| Predicate | Допустимый positive provenance | Недостаточный proxy / divergent case |
|---|---|---|
| CAS bytes и selected view совпадают | `recomputed` через Core resolver/hash/profile validation | Ref правильной формы или одинаковый payload ID при другом profile |
| Result действительно выбран текущей попыткой | `recomputed` из guarded owned tuple/history | Caller run_id, producer role или отдельно существующие CAS refs |
| Compiled law связывает output и выбранную candidate metric | `recomputed` исполнением registered law против actual input/axes/selected semantic definition | Совпавшие unit/name/shape при другом population/denominator/time |
| Actual executable соответствует replay profile | `independently_reconciled` с verified build/runtime boundary; отсутствие доказуемой boundary → `not_established` | ABI/Git SHA/seed/строка build без реально разрешённой identity |
| Compute work не превышает declared process slot cap | `recomputed` из controlled owner history **и** `independently_reconciled` execution-boundary observation как отдельный predicate | Requested workers, один active_count, cap другого pool, неучтённый retained running attempt |
| Все задачи конечного configured workload исполнены/учтены | `recomputed` join полного declared roster с actual outcomes/refs; qualifying roster provenance отдельно | Сумма пересекающихся PASS, потерянные overflow jobs, cap-only trace |
| HTTP input дошёл до правильного method/result | `recomputed` из immutable requested/admitted refs, consumed result lineage и fresh persisted readback | DTO поле существует, internal enqueue работает, cached POST response |
| Access/governance разрешают конкретное действие | `recomputed` по authenticated context и существующей policy при admission/use; protected external premise должна быть проверена отдельно | Tenant из request, producer label, default public classification |
| Scientific adequacy / fiscal law / permission / currentness | Пока только внешняя декларация — `institutionally_supplied`; пока нет inputs — `not_established`; положительное authority use только после применимой проверки и `independently_reconciled` evidence | Unit conversion или replay выданы за law/calibration/custody |

Для составного gate фиксируются отдельные labels его зависимостей, не усреднённая зелёная оценка. `consumer_asserted`, `institutionally_supplied`, `not_established` не несут authority-grade positive; degrade/refuse именно затронутый claim. Candidate с объявленным unknown допустим, если security/resource predicates собственного действия установлены. При protected use volatile predicates проверяются заново; historical label сохраняется как historical evidence, а не обновляется задним числом.

Purpose projections: AD01 `authoritative_for` ограничено проверенной source/output/derivation/representation relation в выбранной boundary; `may_not_use_for` включает scientific identification и publication без их собственных gates. AD02 — observed process slot invariant, не CPU/RSS/deployment guarantee. AD03 — consumed typed input/method lineage, не authentic source. Использовать существующие purpose/status carriers и consumer enforcement; этот текст не вводит новый universal header или status lattice.

## Граница своего решения и genuine external input

| Вопрос | Исполнитель должен решить сам | Чего нельзя выдумать |
|---|---|---|
| Реальный metric | Compile candidate metric definition, typed law, output capture и objective wiring | Калибровку/causal identification, чужую fiscal sign/alias convention, внешний FX/deflator |
| Compute | Реальный scope/cap unit, полный configured local roster, cancellation и no-drop semantics | Production roster/common deployment identity, если заявляется именно production property |
| Observational HTTP | Exact input/method protocol, real HTE normalizer, reader/migration/fresh GET | Issuer permission, authentic provenance, live served root/currentness, научную достаточность источника |
| Missing semantic owner | Найти existing owner/contract; предложить минимальную typed extension и bounded candidate meaning | Подмену внешней authority caller declaration или LLM hypothesis |
| Backend/replay | Установить доступность и actual selected backend/build; явно ограничить unsupported profile | PASS неисполненного backend или исторического build, которого нет |

Нельзя возвращаться с «нужно решение G» для уже выбранного B/A compatibility, serial folds или unit boundary. Для настоящего нового contract counterexample предоставить source pointers, property, divergent case, reuse/extend alternatives, выбранную рекомендацию, footprint/migration и минимальный falsifier. Сначала проверить, не является ли проблема обычным engineering defect или тем же P40 классом глубже. Не откладывать собственную реализацию из-за независящего внешнего law: candidate compute может быть честно limited.

## Conditional K_ref: пока streaming, не paging

Нынешний eager builder читает whole-result intermediates, затем создаёт map и immutable copy; downstream atom/coverage/FTS тоже удерживают память. Source streaming не гарантирует устранение последнего floor, но это первая existing-owner работа. Сохранить selected source/generation/profile, temporal next-start rules, row coverage, duplicate-key winner и observable iteration order; current reference digest не заменять Merkle root.

Сначала найти exact identity held candidate и public companions, выполнить его composed parity/removal/source-replacement. Не приписывать неназванные 19 paths соседнему 16-path proposal. Затем при разрешённых ресурсах измерить полный естественный consumer route и retained map/copy/atoms/FTS phases, actual process high-water/OOM evidence и completion, не только exit signal или fixture estimate.

- Если весь путь помещается — оставить eager immutable representation.
- Если bottleneck wall time — исправлять измеренную фазу, не объявлять pagination лекарством.
- Если после streaming именно unavoidable retained full-view floor превышает нужный бюджет — отдельный конкретный выбор bounded eager refusal либо paged immutable CAS generation.

Будущий paged вариант потребует generation manifest, complete row count/order/key ranges, chunk/profile/hash verification, bounded cache, duplicate/temporal semantics и совместимый legacy semantic root hash. Consumers не должны сразу восстанавливать полный dict/tuple/index. Это **не принятая сейчас representation** и не поручение делать страницы авансом.

## Исполняемый промпт unified local agent

> Продолжай E02 на своём текущем admitted source, сначала reconcile delta с G architecture package `integration/architecture-decisions-2026-10-20`. Реализуй выбранные AD01/02/03 целиком по waves и acceptance matrix. D01–D08 сохраняются. Сначала wire-existing, затем extend; отдельные provenance engines, schedulers, unit algebra и paged K_ref не создавать. Source acceptance и finding closure разделять. Назначай прямых помощников по независимым механизмам с одним writer общих carriers и отдельными reviewers; не вводи дочернюю иерархию. Используй необходимый параллелизм интеллектуальной работы, сериализуй фактически общий compute/memory/scratch. Сохраняй bounded outputs и полные deciding logs. Работа G была design-only и не даёт новых PASS.
>
> Не останавливайся на source-only prototype или «нужна архитектура»: конкретные contract choices в пакете уже выбраны. Сначала исследуй возможность решить каждую проблему существующим owner и реализуй собственные engineering parts. Если действительная scientific/institutional authority отсутствует, сохрани honest candidate limitation и исполни независимую часть; exact external inputs и причину невозможности перечисли отдельно. Новую архитектурную развилку возвращай только с evidence, alternatives, рекомендацией и falsifier. Для source freeze запроси/сформируй explicit integrated checkpoint, затем один дорогой replay после independent reviews. Сохраняй append-only историю, не меняй main без отдельного разрешения; правила публикации текущего coding task продолжают действовать.

Pattern pass при closeout: P01/P02/P03 полнота цепи; P04/P05 candidate/authority/partial; P07/P08 replay/time; P10 metric adequacy; P14 независимость; P27/P31 canonical owner; P29/P32/P37/P38 property-based proof; P39 полный footprint с обязательными companions вне cap; P40 class-level repair; P41 собственная/неустановленная краснота. Никакая строка matrix не присваивает closure.
