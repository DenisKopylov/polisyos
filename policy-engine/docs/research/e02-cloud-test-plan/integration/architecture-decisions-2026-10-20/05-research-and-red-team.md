# Исследование, альтернативы и независимая критика

Дата исследования 2026-10-20. Source pin `11ff2421e04223fc961dd5a520768fd75bafe1e2`. Это объяснение архитектурного выбора, не benchmark и не runtime validation. По запрету пользователя не запускались tests/imports/builds/installers/model checkers; не клонировались внешние проекты. Внешние материалы — первичные спецификации, документация разработчиков и оригинальные papers.

## Что исследовали параллельно

Полный denominator прямых ролей: **16**. Три роли method/metric (source, SOTA, red team); три budget; три HTTP; custody crosscut; migration; original criteria; independent oracles; quantity semantics; conditional paging; minimalism. Это 9 + 7 ролей, не 16 независимых подтверждений одного свойства. Helpers не создавали детей и не писали product source. После первого раунда root свёл противоречия, изменил решения и передал actual документы на дополнительную критику. Research notes не являются code acceptance.

Расхождения разрешались по evidence, не голосованием. HTTP SOTA/minimalism допускали A, repository/red-team предпочитали B; итог — B как действительный versioned capability и A как явная нормализация существующего legacy input. Два отчёта переносили production-only prerequisite в B56; проверка original B56 и D03 сняла это добавочное условие. Аналогично whole-graph replay на каждый GET отклонён: он не создаёт научную независимость и связывает стоимость чтения со стоимостью исторического исполнения.

## AD01: реальные системы lineage, executable identity и units

| Первичный источник | Что он реально решает | Вывод для PolicyOS и предел переноса |
|---|---|---|
| [TFX ML Metadata](https://www.tensorflow.org/tfx/guide/mlmd) | Связывает artifacts, executions и events; позволяет находить input/output конкретного pipeline run | Перенять связи execution→actual artifact. Metadata record сам не доказывает истинность metric или доверие producer; новую MLMD БД не внедрять |
| [Workflow Run RO-Crate / Provenance profile 0.5](https://www.researchobject.org/workflow-run-crate/profiles/0.5/provenance_run_crate/) | Отделяет workflow step, tool invocation, inputs и intermediate outputs | Нужны occurrence IDs и actual output inventory, а не один MethodSignature. Не обещает PolicyOS authority |
| [CWL Workflow v1.2](https://www.commonwl.org/v1.2/Workflow.html) | Явные связи workflow ports/steps и execution structure | Compiled node/slot binding лучше эвристики имени. Переносить workflow engine/его type system не нужно |
| [in-toto Statement v1](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md) | Разделяет subject identity и typed predicate | Execution bundle должен называть exact subject; форма statement не удостоверяет signer/run |
| [SLSA build provenance 1.2](https://slsa.dev/spec/v1.2/build-provenance) | Разделяет build definition, external parameters, resolved dependencies и run/builder | Разделять caller intent и resolved executable context. Builder trust — отдельная premise; record shape и ABI не proof |
| [QUDT schema](https://qudt.org/doc/2026/09/DOC_SCHEMA-QUDT.html), [UCUM](https://ucum.org/ucum) | Различают units/quantity kinds/dimensions; UCUM описывает специальные нелинейные шкалы | Совпадение dimension не устанавливает metric meaning. Использовать узкую typed relation, не импортировать ontology как authority |
| [Pint nonmultiplicative units](https://pint.readthedocs.io/en/stable/user/nonmult.html), [currency contexts](https://pint.readthedocs.io/en/0.25.1/advanced/currencies.html) | Offset/absolute-vs-delta и context-dependent conversion требуют отличных от multiplier правил | В Foundry scale-only Unit нельзя спрятать affine, FX или time law. Не устанавливать Pint для E02 |
| [NumPy RNG compatibility](https://numpy.org/doc/stable/reference/random/compatibility.html) | Условия воспроизводимости зависят от generator/build/call sequence и окружения | Seed и ABI не executable/replay identity; сохранять selected actual backend/RNG/build |

**Наш вывод, не требование стандарта:** existing CAS + guarded run owner + compiled executable law дают более узкую и проверяемую архитектуру, чем новая универсальная provenance/quantity платформа. Цепь hashes доказывает целостность bytes, controlled run commit — принятую попытку, semantic law — конкретное вычисление. Ни одно не доказывает научную adequacy автоматически.

Отвергнутые альтернативы: оставить current refs (bridge остаётся missing); назначить unit по registry/name (P38); перевести все dict в QuantityValue (не решает origin/meaning); новый execution capsule engine (дублирует owners); полный graph replay на GET (дорого, возможны side effects, всё ещё same-code); transitive proof ladder без declared build boundary (неограниченная работа).

## AD02: вложенные задачи и реальные пределы permits

| Источник | Проблема / механизм | Применение и ограничение |
|---|---|---|
| [Ray resources](https://docs.ray.io/en/latest/ray-core/scheduling/resources.html) | Resources — logical admission, не физическая CPU/RAM isolation | Worker-slot cap нельзя назвать hard CPU/RSS cap; native threading и actual memory измеряются отдельно |
| [Ray nested tasks](https://docs.ray.io/en/latest/ray-core/tasks/nested-tasks.html) | Blocking parent может отдавать CPU scheduling resource; разные виды ресурсов имеют разную lifetime | Нельзя «отпустить permit» и забыть удерживаемую память/другой ресурс. Не копировать yield-правило для всех ресурсов |
| [Dask launch tasks from tasks](https://distributed.dask.org/en/stable/task-launch.html), [worker_client implementation](https://distributed.dask.org/en/stable/_modules/distributed/worker_client.html) | Parents могут занять все threads и ждать children; secede/rejoin меняют scheduling occupancy | Cap-1 hold-and-wait — реальный deadlock class. Serial folds устраняют текущую необходимость child fanout; не нужен Dask deployment |
| [AnyIO thread cancellation](https://anyio.readthedocs.io/en/stable/threads.html), [API](https://anyio.readthedocs.io/en/stable/api.html) | Caller cancellation не обязательно останавливает thread; limiter — отдельная capacity abstraction | Lease живёт до физического finish/cleanup, lifecycle timeout не release |
| [Trio core](https://trio.readthedocs.io/en/stable/reference-core.html), [process API](https://trio.readthedocs.io/en/stable/reference-io.html) | Structured cancellation и borrower limits; process termination отличается от abandon thread | Не смешивать task status и ресурсную жизнь; scalar limiter не готовая hierarchy/vector budget |
| [Dominant Resource Fairness, NSDI 2011](https://www.usenix.org/legacy/event/nsdi11/tech/full_papers/Ghodsi.pdf), [Gavel, OSDI 2020](https://www.usenix.org/system/files/osdi20-narayanan_deepak.pdf) | Fair allocation нескольких ресурсов / heterogeneous accelerator throughput | Исследованы как более сложные alternatives. Для uniform process slots без измеренных weights избыточны; не выбранные алгоритмы E02 |

**Наш вывод:** текущему criterion достаточно common owner + serial folds + complete workload witness. Финальный самостоятельный проход уточнил extension с обеих сторон dispatch: refs queue и materialization **до**, serialization/persistence **после** выполняются под тем же worker lease; наружу refs. Fingerprint уже расположен внутри executor. Нужны cancellable handles/backpressure. FIFO выбран честно; root fairness/DRF не приписываются текущему ThreadPoolExecutor. Physical resource guarantees потребуют отдельного platform enforcement, не добавления красивых weight fields.

## AD03: typed artifacts, presence и temporal meaning

| Источник | Полезный pattern | Что он не устанавливает |
|---|---|---|
| [Kubeflow typed artifact inputs/outputs](https://www.kubeflow.org/docs/components/pipelines/user-guides/data-handling/artifacts/) | Typed input/output carriers и lineage вместо случайного dictionary | Artifact type не подтверждает observational law, issuer или currentness |
| [OpenLineage examples](https://openlineage.io/docs/spec/examples/) | Разделение job/run и dataset context/facets | Lineage emission не приёмка source truth и не tenant permission |
| [Feast point-in-time joins](https://docs.feast.dev/getting-started/concepts/point-in-time-joins) | Temporal lookup должен соотноситься с event time | Readback time не source time; point-in-time join сам не гарантирует correction/custody/currentness |
| [JSON Schema object semantics](https://json-schema.org/understanding-json-schema/reference/object), [OpenAPI 3.1.2](https://spec.openapis.org/oas/v3.1.2.html) | Presence/required и null — разные contract состояния | Optional-by-absence не значит nullable; generator должен сохранить эту разницу |
| [Google AIP-180 compatibility](https://google.aip.dev/180) | Изменение API требует source/wire/semantic compatibility | Additive поле не автоматически безопасно для old strict reader, state rewrite или changed defaults |
| [SLSA artifact verification](https://slsa.dev/spec/v1.2/verifying-artifacts) | Проверка provenance требует сверить identity и доверенную policy | Самоприсвоенный producer/method label не attestation |

**Наш вывод:** один явный protocol до parsing, immutable requested intent и owner-resolved admitted intent. B реальный HTE producer; A explicit normalization. SLSA parsing допускает некоторые null/empty equivalences для своего формата — **не переносим их** на строгий HTTP request PolicyOS. Не перенимаем из lineage systems предположение, что любой поступивший facet является доказанным фактом.

## Red-team: атака → изменение механизма

R1 атаковал исходные рекомендации; R2 атаковал уточнённые root решения. Следующие изменения внесены в actual документы до заключительного review:

| Атака / divergent case | Исправление, принятое G | Что намеренно остаётся limited |
|---|---|---|
| Caller пишет правдоподобный CAS bundle с run_id | Guarded atomic owned attempt tuple и обязательный owned context для origin claim | Standalone CAS read доказывает только consistency |
| Binding↔graph/plan и receipt↔result образуют hash cycle | One-way CAS write DAG; bundle не ссылается на будущий result/commit | Нет переписывания historical manifest |
| Поздний attempt меняет current result или смешивает две refs | Fenced atomic pointer tuple, idempotence только exact tuple | Superseded bytes доступны лишь как explicit historical diagnostic |
| Whole-job failure стирает полезный sibling output | Eligible committed occurrences сохраняются в existing partial status calculus | Failed/cancelled occurrence не даёт output authority |
| Семантические labels совпали, inputs/population нет | Law реально проверяет captured refs/axes/denominator/time; no name heuristic | Неустановленная science не становится identification |
| Дорогая упаковка всех arrays и replay каждого GET | Полный inventory, selected payloads один раз; persisted typed projection и bounded fresh reader, cache только ускорение | Невозможный capture/replay profile остаётся unavailable; missing projection не запускает compute из GET |
| Slots/worker metadata выданы за CPU/RSS bound | Явная process slot unit; native thread/RSS limitation | Hard physical cap не заявлен |
| Executor cap взят после array allocation | Lazy/ref-based input bridge до materialization у того же owner | Old pre-materialized API имеет отдельную limitation |
| Output serialization и late callback обходят worker boundary | Persist внутри admitted callable; completed handle только refs; heavy callbacks через тот же owner | Dispatch-only historical receipt не доказывает новую границу; slot всё ещё не hard RSS cap |
| Registry изменился между POST и первым start | Method/defaults/runtime pin до acceptance; content admission проверяет сохранённый выбор | Unavailable pin даёт refused/limited по конкретному свойству, не latest substitution |
| Timeout освободил slot, а native callable жив | Release только actual finish; retry также занимает capacity; fence блокирует stale publish | Hung worker не имеет bounded liveness guarantee |
| Unbounded FIFO объявлен finite/fair/cancellable | Реальное extension queue/handle/backpressure; выбран FIFO без root-fair обещания | Arbitrary nested fanout не принят |
| Envelope discriminator исчез, parser ушёл в raw | Явный request protocol до decode; no sniff fallback; required raw wire version | Legacy только explicit A |
| Нормализация затёрла submitted source | Requested и admitted intent разные; raw source parent edge | New envelope не делает source authentic |
| Method FQN/ABI совпал, code/defaults изменились | Resolved build/version/canonical effective params и pinned resume | Missing historical build → limited replay |
| Сначала проверили profile, потом перечитали default view | Один guarded selected snapshot/stream; full-view authorization | Нет утверждения о найденной live tenant exploit |
| Derived envelope получил default public classification | Existing governance join + explicit inheritance; access на read/release | Candidate mode не privacy waiver |
| Числа проверили после giant JSON/NumPy copy | До materialization bounded bytes/depth/elements под lease; no duplicate decode | Logical cap всё ещё не hard RSS cap |

P40: большинство повторных замечаний — тот же класс trust-by-form/proxy one level deeper; решения расширены у owner, не per-test patches. После этого unsupported scientific/replay/physical-resource классы имеют явную bounded limitation и falsifier. Следующий hypothetical тип/метод не требует новой универсальной платформы.

## Границы итогового review

Заключительный independent document review назначен отдельно на actual AD01, AD02, AD03, crosscut minimalism и independent-oracle design. Его итоговые dispositions фиксируются в companion `review-disposition.md`, после внесения обязательных исправлений. Ни один GO документа не является GO кода или доказанным новым runtime property.

Research notes хранятся ignored под `_build/`, содержат source pointers и рекомендации, иногда отвергнутые root. Этот пакет — согласованное решение, а не механическая сумма notes. Raw dumps, copies tracked source, production data и большие archives в него не включены. Полные runtime deciding logs появятся только у исполнителя после реальных future checks.
