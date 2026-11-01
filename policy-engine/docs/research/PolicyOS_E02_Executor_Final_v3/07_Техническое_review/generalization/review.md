# E02: независимый cross-lane review способности, переносимости и силы доказательств

**Срез:** 2026-11-01. **Основание:** repository `20d9009be21097bfbdc38a546a15cc60213b8ace`; immutable executor baseline. **Статус:** завершён read-only review, **не** валидация реализации. Product tests, installs, native imports и live providers не запускались.

`P` ниже — `e02_final_technical_review/baseline/PolicyOS_E02_Executor_Specifications`; `R` — `e02_repository/policy-engine`. Точные хеши/диапазоны — `coverage.json`. Структурированные выводы — `findings.json`; внешние источники — `sources.json`; технологические решения — `library_decisions.json`.

## 1. Главный вывод

**Основную конструкцию комплекта следует сохранить, а не переписывать.** Он действительно направлен на полезную расширяемую систему: общий compiler/resolver, discovery/binding, реальные численные owners, сохранённые результаты, продолжение по новому основанию, свежие consumers и ограниченная переносимость. Это не просто 608 проверок отказов. Но даже будущий зелёный прогон всех предложенных проверок будет доказательством **конкретного набора механических и интеграционных свойств**, а не автоматическим подтверждением качества любого policy design, автономной постановки новых задач или эмпирической истинности моделей.

Содержательно важны четыре уточнения:

1. **GEN-01 — целевое уточнение процедуры X03.** Принцип heldout уже присутствует в JSON, а ручной второй профиль уже запрещено называть самостоятельной generalization. Не хватает наблюдаемой процедуры: что замораживается до независимого выбора verification case, какие изменения разрешены, когда пример становится development вместо verification. Это устранение неоднозначности доказательства, не найденный runtime bug.
2. **GEN-02 — условная квалификация discovery.** Явный construct, успешно разрешённый injected resolver, ещё не доказывает, что actual request/query найдёт новый подходящий ресурс среди отвлекающих. В репозитории уже есть recall/freshness owners: надо связать существующее измерение с выбранной сквозной историей, а не создавать ещё один framework. Конкретные локальные изменения для embedding/relevance принадлежат соответствующему packet review.
3. **GEN-03 — измерять до оптимизации.** Source resolver делает linear scan, но текущий persisted fallback содержит всего **3 capabilities**. Объявлять это неоптимальным и срочно вводить индекс было бы неверно. Для сильного claim «дешёвое free-grow» нужен workload/cost evidence, после него — решение об access plan.
4. **GEN-04 — конкретизировать уже честно сохранённые X04 gaps.** Capacity и same-result lifecycle **уже** выделены в `BIND-X04-E01/E02`. Приведён небольшой независимый oracle, который поможет закрыть их содержательно, без универсального allocator или нового event store.

Нет оснований блокировать все 127 ремонтов до появления универсального benchmark, полного MCTS, реального государственного мандата или любых внешних данных. Нет оснований и называть scoped mechanical PASS «универсальной policy-компетентностью».

## 2. Что уже хорошо и нельзя ослаблять

### 2.1. Польза, а не refusal-only

`P/00_Общее/Правила_исполнения_и_приёмки.md:11–20` требует positive path у actual consumer, запрещает expected-result substitution, различает empirical/permission, сохраняет useful partial. В X01 отказ первого метода должен сопровождаться исполнением подходящего; X02 требует реальное потребление нового основания, не только job-complete; X03 требует иной смысл, не UUID; X04 — joint result и дальнейший пересмотр.

Поэтому «always refuse» **уже не может законно закрыть** этот комплект. Изобретать новый аналогичный общий guard не нужно. Нужно проверить исполнение существующего положительного требования.

### 2.2. Настоящие владельцы и сохранение смысла

Все 12 shared contracts повторяют правильное правило: если принимается storage — настоящий store/fresh reader; numerical method — настоящий backend; physical cleanup — настоящий OS resource. Controlled provider/encoder законен за границей проверяемого свойства. Один общий scenario может покрыть несколько REQ только своими конкретными assertions и binding, а не своим названием.

Это оптимальная альтернатива двум крайностям: тяжёлому full-platform E2E после каждой строки и десяткам success-shaped mock tests. Сохранять local matrices — они не становятся ненужными после одного красивого cross-lane demo.

### 2.3. Направление архитектуры не превращено в догму

Vision Rule12 (`…vision-and-organizing-rules.md:201–230`) требует capability-from-corpus и предупреждает о false abstention. Но GREQ-10/X03 правильно уточняют: новый **совместимый** ресурс не требует case routing; действительно новая общая семантика может требовать код. Governed vocabulary, schema и конечный status enum не равны capability whitelist.

Аналогично встроенный bootstrap одного economics module в `R/src/polisyos/foundry/plugins/discovery.py:44–64` сам по себе не доказывает закрытый мир: рядом есть installed-entry-point discovery (`:67–89`) и другие extension paths. Проверять нужно, проходит ли реально новый compatible extension до нужного consumer, а не запрещать все литеральные списки.

### 2.4. Сохранена разница между механикой и основанием

Target architecture не обещает всемогущество (`…target-architecture-and-gap.md:559–616`); identity/CTM допускают демонстрацию механизма без присвоения институциональной authority и требуют исторической/текущей различимости. Текущий комплект это в основном соблюдает. Synthetic causal model может быть честным conditional calculator; causal truth исходной модели и полномочие на действие остаются отдельными вопросами.

## 3. Что именно может быть принято

Ниже — язык reviewer-решения, **не предложение нового runtime status registry**.

| Решение | Достаточное свидетельство | Чего оно не доказывает |
|---|---|---|
| Ремонт принят | Старый различающий контрпример, исправленный valid input, preservation, actual owner/consumer выбранной boundary | Качество всей lane или другого backend |
| Механизм квалифицирован в указанном профиле | Native selected implementation, independent oracle, persisted/fresh path где нужен, error/state/resource controls | Реальную пригодность модели или автономную постановку |
| Ограниченный transfer показан | Замороженный общий механизм + независимо выбранный совместимый случай + честный manual/code/cost ledger | Любые домены/масштабы, незаявленные сочетания осей |
| Практическая задача подтверждена | Согласованные доступные данные/права, предметные критерии, baseline/comparator, независимый heldout, экспертная проверка необходимого свойства | Необъявленное causal/production использование |
| Protected действие допустимо | Дополнительные действующие role/scope/currentness/permit основания именно этого действия | Не создаётся автоматически предыдущими PASS |

**Тестовая зелень не складывается в силу утверждения.** Один и тот же shared run, процитированный десятью пакетами, остаётся одним наблюдением. Разные assertions могут законно покрывать разные свойства, но не дают десять независимых подтверждений.

## 4. GEN-01: две известные задачи против независимого transfer

### 4.1. Точная неоднозначность

X03 MD (`:23–33`) требует иной случай, второй oracle, manual diff и допускает generic code extension. JSON уже содержит:
- `global_rules`: independently selected held-out для domain practical validation;
- `cross_lane_stories[E02-X03].negative_oracle`: заранее вручную собранный второй profile не является самостоятельным generalization.

**Следовательно, неверно писать «heldout вообще отсутствует».** Отсутствует операциональный протокол, который не позволяет принять tuned second example за independent heldout.

### 4.2. Неправильная реализация, которую известная пара не различает

Общий template/ranking mechanism настроен на две известные структуры, корректно проходит их independent numerical oracles и умеет зарегистрировать новые параметры/ресурсы. В нём нет `if case_id`. Однако новый совместимый structural recombination не возникает: generator выбирает только подготовленные template families. Проверки двух известных примеров не видят этого ограничения. JSON справедливо запрещает делать сильный вывод, но hash/order evidence, который проверяет соблюдение запрета, не задан.

Это **не утверждение, что такой код обнаружен**. Это различающий класс overfitting. Отдельные packet tests могут уже исключать некоторые его варианты; они не заменяют выбранный независимый transfer probe.

### 4.3. Ограниченная замена процедуры

Дополнить существующий X03, не вводя новый harness:

1. После development case зафиксировать relevant code, grammar/model primitives, adapter/configuration schema, package/profile и oracle protocol. Не требуется заморозить весь постоянно меняющийся репозиторий: граница ровно та, от которой зависит проверяемый путь.
2. Независимо выбрать один ещё не использованный verification case **в заранее объявленном compatible envelope**. Изменение должно затронуть структуру композиции/контраст/временную постановку, а не только числа. Перестановки IDs/порядка — дополнительные cheap metamorphic controls, не самостоятельный второй домен.
3. Разрешить typed input data, реальные coefficients, model/policy IR из уже реализованных primitives и новый compatible resource через existing registration/admission. Новая структура такого IR — законная конфигурация в замороженной schema/operator semantics. Заморозка включает router/decoder/operator implementations. Запретить спрятанный callable, готовую answer table, новую маршрутизацию или ручную смену semantics под этот пример. Ручную model/profile preparation показывать отдельной строкой и не выдавать за autonomous interpretation.
4. Проверить actual owner→persist→fresh consumer независимым analytic/exhaustive/structural oracle. После deciding-input mutation результат обязан адресно измениться либо получить точное limitation.
5. Если нужна новая общая семантика, это законное развитие. Данный пример становится development; после расширения требуется новый freeze и другой fresh verification case для нового transfer claim.
6. Называть результат ограниченно: «переносимость этого механизма в этой области показана». Один heldout не доказывает статистическую надёжность по всем классам.

Для обычного локального finite-number fix всё это не нужно: параметризованные различающие классы остаются достаточными по GREQ-10.

## 5. GEN-02: полезность discovery и proposer не следует из binding

### 5.1. Не объявлять существующие owners отсутствующими

`R/src/polisyos/runtime/quality/proving_ground/legal_mandate_search.py:1867–1962` уже собирает known-seed recall, snapshot/freshness, missed classes и различает `search_ceiling_repair_required` от разрешённого bounded no-ground. Его tests `…test_proving_ground_legal_mandate_search.py:905–960` проверяют шесть классов seeds и missed-seed failure. G5 conversion tests `…test_proving_ground_conversion.py:1995–2025` запрещают grounded abstention при failed recall/stale index.

Это реальная полезная архитектурная механика, а не необходимость нового recall framework. Но проверенный GL путь не квалифицирует автоматически любой другой query adapter, source registry или embedding backend. В выбранном X03 нужен identity-bound join именно с использованным путём.

### 5.2. Concrete divergent case

Source-profile search (`capability_discovery.py:1040–1125`) строит content-bound snapshot и честный ledger. `_owner_search_terms/:2158–2172` объединяет query text и construct terms; `_row_match_count/:2183–2188` требует присутствия всех terms в owner-projected row. Подходящий callable ресурс может существовать, а дополнительные слова ordinary request отсутствовать в его description: lexical search вернёт no-match, direct construct resolver — valid result.

Сам алгоритм **не объявляется багом**: он имеет явно записанный all-terms contract. Ошибка возникла бы только если higher-level consumer выдал такой bounded lexical miss за доказанную недоступность предметной способности. Такое ошибочное исполнение здесь не установлено.

Для automatic-discovery claim достаточно небольшого настоящего witness:
- independently known compatible resource и hard-negative с похожим названием, но иным scope/role;
- actual supported request→query builder, не готовый selected ref;
- до штатного добавления нового ресурса его нет; после publication/refresh он обнаруживается и исполняется без core change;
- distractors, cutoff и stale/withdrawn ресурс различаются; допустимые positive не превращаются в «успешный честный отказ»;
- selected snapshot/ref достигает consumer; current withdrawal не стирает unrelated useful result.

Если продукт обещает только explicit-construct path, именно это и написать: lexical synonym competence не надо добавлять скрытым обязательством.

### 5.3. Постановка и ranking — ещё один уровень

X01 с заранее заданным lawful profile действительно проверяет интеграцию численного механизма. Он не доказывает, что proposer выберет правильную постановку из обычной новой задачи. Аналогично корректный Pareto, posterior или policy update не доказывает экономически хороший next action.

Это уже признанные ограничения, не замаскированные дефекты. Для более сильного «policy designer полезен» добавить отдельный небольшой task-quality probe: заранее допустимое множество alternatives, oracle/baseline, материализованные constraints и явная проверка, не доминируется ли выбранный результат доступной альтернативой. Сравнивать только с информацией, разрешённой в decision-time. Не требовать реального causal regret там, где контрфактической эмпирики нет. Не подменять качество исполнения качеством live LLM; controlled proposal законен только в integration claim.

## 6. GEN-03: стоимость расширения и разумные технологии

### 6.1. Source-level факт и предел вывода

`RequirementToCapabilityResolver.from_duckdb/:464–506` материализует весь slice; `:_evaluate_candidates/553–577` просматривает capabilities для каждого construct. В зависимости от workload это даёт затраты порядка числа запросов × размера registry, плюс загрузка/парсинг. Но actual fallback в `runtime/quality/generation_cycle.py:10152–10174` вызывает `governed_fixture`; его JSON имеет всего **3 capabilities, 3 acquisition strategies, 1 failure mode и 11 688 bytes**. DuckDB constructor здесь не доказан hot path.

**Правильное решение сейчас — не навязывать индекс.** Маленький immutable scan может быть проще, быстрее и надёжнее. BIND-X03-E01 уже требует стоимость первого/второго случая; для масштабного claim расширить запись actual corpus size, constructions, query count, input/output bytes, expensive calls, cold/warm time и peak RSS. Частота reload важнее одного Big-O.

Только после измерения выбирать: сохранить scan; один snapshot-bound `dict[normalized_construct, tuple[rows]]`; selective projection в существующем DB owner. Не выбрасывать rejected alternatives, conflict/authority checks ради скорости. Для SQL изменения сравнить actual plan и семантически одинаковые результаты на locked backend.

### 6.2. Технологические сравнения

- **Plugin discovery:** Python3.14 stdlib уже предоставляет installed distribution entry points, selection и loading. Existing `core.discovery.list_entry_points/:112–130` использует этот API. Новый plugin framework не даёт нужной semantic qualification; расширить существующий owner и actual installed-consumer test. [Python 3.14 importlib.metadata](https://docs.python.org/3.14/library/importlib.metadata.html).
- **Registry access:** versioned DuckDB1.4 документация описывает tradeoff ART: selective lookup против maintenance/memory. Это аргумент измерять, не безусловно индексировать. Проверял именно 1.4 после redirect stable→2.0; проект locked1.4.3 не предлагается обновлять. [DuckDB 1.4 indexing](https://duckdb.org/docs/1.4/guides/performance/indexing).
- **Cache/CAS:** полезный established comparator — разделение action cache и content store. Оно не заменяет current admission и не доказывает правильность математики. Existing E02 owners сохранить; Bazel не предлагается внедрять. [Bazel remote caching](https://bazel.build/remote/caching).
- **Provenance:** W3C PROV даёт общий язык entity/activity/agent/derivation. Это не повод мигрировать все artifacts в RDF или единый persisted event envelope. Existing CTM/family owners лучше сохраняют специфические meaning/time/authority contracts. [W3C PROV-DM](https://www.w3.org/TR/prov-dm/).

Точные решения/альтернативы/locked context — в `library_decisions.json`. Общие рекомендации по testing libraries приведены в сводном обзоре; здесь не предлагается ещё один property/mutation framework и не присваивается чужая проверка зависимостей.

## 7. GEN-04: маленький сильный X04 вместо грандиозной платформы

### 7.1. Shared resource — это не любое нелинейное слагаемое

`BIND-X04-E01` уже прямо говорит: `y=u+2a+3b+4ab` показывает interaction, но не имеет самостоятельного capacity contract. Следовательно, это **не новый пропуск спецификации**.

Если выбран существующий capacity owner, полезен конечный пример. **Здесь предлагается ровно feasibility contract:** суммарный demand выше capacity делает выбранную программу infeasible; автоматического allocation, rationing, capped outcome или permission на действие из этого не следует. До запуска owner должен действительно выразить demand/capacity/outcome, а пользовательская составная программа — потребить этот контракт. Если действующий owner имеет другую семантику (например, capped service), oracle строится по ней отдельно, а не подменяется этой таблицей:

| Действия | Demand | Benefit | При capacity10 |
|---|---:|---:|---|
| A | 4 | 5 | feasible |
| B | 4 | 4 | feasible |
| C | 4 | 3 | feasible |
| A+B | 8 | 9 | feasible, optimum |
| A+C | 8 | 8 | feasible |
| B+C | 8 | 7 | feasible |
| A+B+C | 12 | 12 | infeasible |

Полная таблица с empty subset — `independent_capacity_oracle.json`, вычислена **независимой stdlib арифметикой, не product test**. Pairwise-only feasibility ошибочно допустит тройку. Значение optimum9 — независимая справка для случая, когда выбранный search contract действительно максимизирует этот benefit; от простого capacity owner не требуется новый optimizer. Capacity12 должна допустить её: иначе always-reject проходит negative, но проваливает positive. Перестановка IDs/порядка/группировки не меняет смысл. Реальный selected producer обязан передать capacity/conservation и joint result actual persisted consumer, который изменяет ответ по программе. Отдельная проверка `12>10` без этого пути не считается joint capability.

Если такого owner нет, законный результат — закрыть local numerical repair, сохранить useful conditional joint algebra и назвать resource ability `NOT_ESTABLISHED`. Нельзя дописать фиктивную универсальную «allocation policy» только ради PASS.

### 7.2. Один результат до и после изменения

`BIND-X04-E02` уже требует общий before/after witness. Сделать его различающим помогает dependency diamond внутри существующего actual program/result owner (не отдельная игрушечная graph function): источник S питает P и Q, вместе — R; D независим. Изменение/withdrawal S должно:
- изменить current applicability именно зависимого R/P/Q по действующему contract;
- сохранить historical bytes/ref/result и явно историческое чтение;
- оставить D доступным;
- не позволить late old callback воскресить current validity;
- не «омолодить» evidence простым перечитыванием.

Новая observation не обязана менять causal model или scalar result: может меняться только допустимость claim, либо сохраниться explicit disagreement. Same scalar при независимом новом основании тоже не равен unchanged basis. Эти различия уже сильная часть CYC-03; новый test должен связать их с выбранным persisted program и public limitation, а не собрать несвязанные зелёные monitor/UQ tests.

## 8. Все 12 lanes: bounded capability acceptance, а не только пакетные PASS

Следующие планы — **не требование выполнить все строки на каждом patch**. Для lane release/существенного расширения выбрать релевантный минимальный witness; для local fix оставить его companion tests и затронутую boundary. Где контроль уже есть, он помечен как сохраняемый, а не новый «найденный пробел».

### LANE-01 — Candidate cycle, acquisition, simulation, selection

**Вердикт:** сохранить; X03 уточнить по GEN-01, discovery qualification по GEN-02 только в выбранном scope. **Доказуемая способность:** ordinary supported input→actual builder/model/contrast→N5/N8→persisted conditional useful answer; новый lawful source реально используется. E02-I01-A/B/C уже требуют fallback после неподходящего метода, singleton, A→B→B→B→C, current N6 basis и partial retention.

**Что может остаться за пределами PASS:** корректный executor под authored profile, но не умеющий самостоятельно предложить новую admissible постановку. Это законное limitation, пока не заявлен general designer. **Positive/adversarial:** сохранить actual N5/N8, numeric comparator и changed binding; не заменять orchestration ready result. **Transfer:** один frozen compatible-resource case, иной contrast/structure, actual request→discovery, independent oracle. **State/cost:** fresh process reader, unchanged B не вызывает повторного expensive N5, C меняет basis; source withdrawal ограничивает affected claim; считать actual calls, ручную подготовку и cost, не только result count. **Не повышать:** technical readiness/conditional simulation не production mandate.

### LANE-02 — Search, optimisation, funnel, transfer

**Вердикт:** сохранить repair/native qualification; stronger search-quality claim отдельно. E02-I02-A–D уже проверяют run isolation, delayed tells, actual MethodJob, posterior/resume, Pareto, split funnel accounting, protected writer permit и transfer freshness. Это существенная capability, не mere DTO.

**Неправильный сильный вывод:** детерминированная последовательность точек и корректный posterior гарантируют хороший search. Даже заведомо слабый sampler может законно удовлетворить часть механических contracts. **Positive/oracle:** маленькое конечное admissible множество с independent exhaustive nondominated set и known optimum; сравнение с simple baseline в том же бюджете только для claim о качестве. **Adversarial:** stale tell, incompatible history, same-value but different measurement identity, cap/exhaustion и cancellation уже сохранять. **Transfer:** перестановка dimensions/IDs, иной диапазон/metric direction и одна compatible history, не переиспользовать foreign split. **State/cost:** persisted strategy fresh restore, paid-evaluation count, separate fit/refit cost, one protected commit. Не требовать GP победить на каждом random seed и не выбирать seeds/tolerance после результата.

### LANE-03 — Empirical scope, predictive calibration, backtest

**Вердикт:** сохранить честную bounded qualification. E02-I03-A/B/C правильно различают synthetic calculation, predictive holdout и causal authority; actual forecast/report/receipt/fresh S10, prefix refs и failures находятся в явном scope.

**Что всё ещё может пройти mechanical tests:** очень широкий, мало полезный прогноз с корректно посчитанной coverage. Правильные hits/counts не равны хорошей decision utility. **Positive/oracle:** независимый prefix-only reference расчёт одного ряда; проверить число/width/unit/counts, а для practical forecast claim — заранее выбранный naive baseline и loss/coverage/width на heldout, не только nominal target. **Adversarial:** future leakage, empty/incomplete counts, rule substitution и cancellation уже предусмотрены. **Transfer:** второй regime/seasonality или scaled units при frozen fitting protocol; temporal cutoffs и selection не подстраивать по test. **State/cost:** actual persisted full report, fresh receiver, cutoff-bound source versions, fold ceiling before work и failed/unattempted denominator. Предметная evidence остаётся отдельной от синтетического oracle.

### LANE-04 — Compilation, economics, training, conditional calibration

**Вердикт:** сохранить. E02-I04-A/B — реально полезный generic graph/compiler contract; C — tiny actual trainer; D — настоящее conditional execution. Нельзя заменить explicit unsupported HARD training общим запретом useful fluid/relaxed training.

**Граница:** policy изменяется после updates — ещё не улучшение policy. PLG-03 это честно ограничивает; не объявлять такое ограничение дефектом. **Positive/oracle:** nonstandard typed parameters/edges, повторяемый метод, numeric output и provenance; tiny trainer сравнивать с independent no-update result. **Adversarial:** cycle/duplicate producer, cache params drift, interrupted publication, unsupported train до rollout. **Transfer:** frozen graph с новой разрешённой композицией/requires-only edge и другим order/ID; для stronger learning claim отдельно frozen evaluation episodes и baseline, без требования универсального RL. **State/cost:** actual checkpoint свежим reader, optimizer/update count, RNG/clock, peak memory и forward count; scalar vs active/inactive branch не меняет semantics.

### LANE-05 — Graph, causal methods, SCM, fit reuse

**Вердикт:** сохранить scoped native methods и отдельные backend profiles. E02-I05-A–C уже используют latent-DAG oracle, independent numerical estimator controls, actual selected worker, CAS/fresh query и запрет подмены DoWhy route native_hybrid.

**Граница:** правильное вычисление на выбранном graph/estimand не подтверждает, что он соответствует реальному миру. **Positive/oracle:** small graph enumeration/structural oracle отдельно от tested graph API; small exact model с independent analytic intervention/comparator. **Adversarial:** stale graph version/cache, row/mechanism tampering, missing relevant vs irrelevant roots, point-only backend без выдуманного CI. **Transfer:** одна ранее не использованная topology/latent-confounding pattern в supported static profile, затем явный out-of-profile PAG/temporal case. **State/cost:** fit→persist→fresh selected worker/reader с current diagnostics; измерить fit reuse отдельно от downstream queries. Не вводить «универсальный causal backend» ради унификации incompatibilities.

### LANE-06 — State, execution, resume, CAS, migration

**Вердикт:** сохранить существующие owners и пять integration variants. Это инфраструктурная lane: её useful capability — безопасно исполнить/продолжить настоящий расчёт и не потерять partial, а не дать самостоятельную policy-рекомендацию.

**Граница конечной evidence:** несколько линейных traces не доказывают произвольный workflow/interleaving. **Positive/oracle:** независимый small reference state machine и выбранный diamond DAG; serial uninterrupted result vs две остановки/resume совпадают по semantic output/refs. **Adversarial:** write after lease takeover, canceled publication, corrupt checkpoint, namespace collision, foreign cleanup file — существующие controls сохранить. **Transfer:** другой dependency shape и partition/rebatch schedule, не exhaustive scheduler model checking всей платформы. **State/cost:** actual process/pipe/FD/store, fresh reader, exactly-once protected write в выбранной boundary, paid retries/peak memory; CAS identity отдельно от admission. Исторический профиль читается без переписывания bytes.

### LANE-07 — Ukraine intake, composition, calibration observations

**Вердикт:** сохранить source-specific intake и generic composition; не выдавать три источника за любые demographics. E02-I07-A/B/C требуют реальные raw/snapshot handoffs, primary precedence per cell, contributors, exact numeric reduction и observation alignment.

**Что не следует из PASS:** что lawful source values содержательно полны/верны или mapping к target всегда предметно корректен. **Positive/oracle:** independently authored маленькая cell table с duplicate keys, fractional donors и units/time; expected target bundle не вычислять тем же join/normalizer. **Adversarial:** missing vs measured zero, invalid calendar, source conflict, tampered projection уже в контракте. **Transfer:** frozen compatible source с другой row partition/order и новым разрешённым schema/profile; совместимые units проверить по физическому oracle, несовместимые не auto-convert. **State/cost:** restart после partial yield без повторного prefix, second JOIN/fresh read сохраняет lineage; bounded audit detail не уменьшает total counts. Реальная policy applicability требует отдельного source/target domain review.

### LANE-08 — Catalog, embeddings, ingest

**Вердикт:** сохранить generation/publication/stream mechanics; actual usefulness retrieval квалифицировать в выбранном served profile. E02-I08-A/B/C уже сильны по loaded-assets/content binding, failed generation retention, owned Legal route, restart/rebatch, real FD и rate/circuit controls.

**Неправильный сильный вывод:** правильные vector IDs/float32/current manifest означают полезный поиск. Сортировщик, всегда возвращающий первый документ, может проходить слишком бедный одно-документный witness; соответствующий локальный oracle уточняется packet reviewer, а не выводится здесь из неполного чтения его tests. **Positive/oracle:** сначала synthetic non-tied vector topology vs independent exact dot/cosine; отдельно небольшой pre-adjudicated actual-encoder relevance set, если заявляется semantic retrieval. Это разные claims. **Adversarial:** stale model/tokenizer/intent, withdrawn row, distractor с похожим именем, mixed generation и failed stage. **Transfer:** newly published compatible document/resource, frozen encoder/query rules и current generation; no-match не превращать в доказательство отсутствия capability. **State/cost:** actual index reopen/served consumer, native ANN claim только native backend, actual chunk/FD/permit accounting. SPILL_TO_DISK unsupported остаётся честным bounded profile, не скрытым обязательством универсального spill engine.

### LANE-09 — Scholar provenance, LLM reuse/accounting

**Вердикт:** сохранить. E02-I09-A/B проверяют настоящие raw bytes/span→docs и exact closed-input reuse с текущей readmission; это правильная защита от «красивая summary = источник» и бесплатной stale authority.

**Граница:** source-exact snippet и deterministic cached translation не доказывают, что выбранный фрагмент отвечает вопросу или правильно интерпретирован. **Positive/oracle:** local controlled raw documents с заранее заданными spans/claims; byte extraction oracle независим от parser. Для semantic-quality claim нужен отдельно adjudicated question/result, не только substring. **Adversarial:** shifted span/wrong kind/foreign ref, forbidden cached destination, scope/epoch drift, waiter cancellation — сохранять. **Transfer:** новый совместимый raw format/provider через существующий контракт и новый closed translator bundle без special routing. **State/cost:** v1/cached v1/v2 historical/current distinction; один provider miss, отдельный consumer ledger/settlement, no double spend; warm output с новой admission не притворяется новым compute. Не требовать live paid API для transport/wiring qualification.

### LANE-10 — Calibration, joint law, sensitivity/stress

**Вердикт:** сохранить численно сильные локальные oracles и честный conditional scope. E02-I10-A имеет конкретные independent objective/gradient/Hessian values и координатное различие physical θ/optimizer-u; B сохраняет joint law/weights/shared rows; C — source-bound designs и failed mass.

**Граница:** правильная derivative или covariance algebra не делает uncertainty эмпирически calibrated. **Positive/oracle:** actual JAX producer vs independent closed form; exact finite atom enumeration для joint output и независимая small design table для sensitivity. **Adversarial:** covariance rank/tiny variance, duplicate source, zero std, filtered draws, wrong law/block integrity, unavailable outputs — сохранять. **Transfer:** другая разрешённая correlation/atom law с асимметрией, смена units/parameterization с правильной chain rule; unsupported law явно вне envelope. **State/cost:** same final snapshot/forward, fresh uncertainty reader, declared stopping reason и attempted/failed denominator, separate startup/JIT vs warm sampling costs. Actual source/fusion/intent owner absent — полезный helper output не засчитывается source-bound PASS (`MAP-CAPABILITY-CONDITIONAL`).

### LANE-11 — Explanation, monitoring, legal comparison

**Вердикт:** сохранить strict wire/currentness и разграничение legal comparison/causal effects. E02-I11-A/B/C действительно проверяют persisted explanation, subject-bound monitoring и norm/report→public consumer.

**Граница:** правильная сериализация explanation не доказывает человеческое понимание; retrieval нормы и legal diff не доказывают governing relation/mandate. Это не недостаток bounded contract. **Positive/oracle:** независимая expected issue-path/severity table и lifecycle state transition для одного selected subject. **Adversarial:** coercible wrong types, nested extras, foreign report, stale basis, structural slash collision — сохранить. **Transfer:** новая compatible normpack/subject structure и unchanged generic parser/reader. **State/cost:** before/after того же результата как GEN-04; историческое чтение не current authority, protective response не causal confirmation; bounded report size/parse time. Для claim о понятности ответа — маленькая отдельная reviewer rubric на исходный вопрос/number/comparator/limits, а не ещё один proof schema.

### LANE-12 — Migration, packaging, generated client

**Вердикт:** сохранить finite census, реальный installed artifact и фактический client→runtime call. E02-I12-A/B правильно запрещают закрывать consumer отсутствие одним grep и не создают второй N6 issuer; CYC-05 owns readiness bridge.

**Граница:** полный объявленный census не доказывает совместимость неизвестных external consumers. **Positive/oracle:** exact wheel/sdist/import origin и public DTO/error/nullability contracts; independent expected response shape, не только generated TS typecheck. **Adversarial:** stale generated artifact, path/query special names, missing facade, unexpected heavy import, source-vs-installed shadowing — сохранить. **Transfer:** один новый compatible installed extension/consumer schema в заранее объявленном finite family, замороженный generic generator; не обещать любую third-party distribution. **State/cost:** fresh process из actual artifact, один согласованный packaging window, reuse evidence only exact same bindings, startup/import memory cost в выбранных profiles. CP6 artifact PASS не заменяет actual current N6 consumer predicate.

## 9. Компактная сквозная программа приёмки

Не создавать «всё-в-одном supertest». Использовать существующие owners и receipts, разделив обязательные join assertions:

### A. Первый полезный результат — X01

Один достижимый supported request; явно выбранные model, units, contrast и limited use. Один непригодный и следующий пригодный method. Actual numerical producer, independent expected result, persist, новый consumer/process, понятный ответ. Отдельно change binding/unit/comparator; unaffected output остаётся useful. Это minimum positive floor, а не empirical promotion.

### B. Получение и реальное использование — X02

Один missing evidence type; actual controlled raw source и lawful projection; A→B→B→B→C. Наблюдать не только equality refs, но actual expensive call count/changed basis. Contradicting source не выбрасывается как неудобный. Raw series не закрывает relation/mandate. Fresh read после interruption сохраняет partial и failed denominator.

### C. Замороженный transfer — X03

После A/B development freeze selected mechanism; independently selected compatible case; resource registered штатно; ordinary supported request/discovery достигает actual execution; independent result oracle. Отдельно manual construction, code/resource additions, compute и cost. Один true out-of-profile control, но positive не исчезает из-за всех authority gates. Для qualitative task usefulness — заранее понятный baseline и ограниченная reviewer rubric, не arbitrary universal score.

### D. Joint composition и изменение — X04

Достаточный existing analytic/simulation/formal owner; independent joint oracle, не naive sum. Capacity subcase только при соответствующем claim/owner; currentness sequence одного persisted selected result. Historical/current outputs и affected dependency cone проверять identity-bound. Unknown causal interpretation не превращать в автоматический model update.

### Evidence checklist для этих четырёх историй

- Relevant code/artifact/profile hashes, actual commands/exit; dependencies и environment из lock, не из случайной audit Python.
- Which property used actual owner; список doubles и исключённых claims.
- Input/selected-resource/model/contrast/source identities; snapshot/time roles.
- Independent oracle protocol и expected values до результата; tolerances/seeds до запуска.
- Positive, adversarial, fresh-reader, changed-basis и transfer assertions по конкретным REQ.
- Actual expensive-call count, manual preparation, cold/warm cost/RSS; failed/unattempted retained.
- Outcome по каждому claim: accepted / limitation / unavailable / not run; не новая merged «green» authority.

Ничто здесь не требует всех 38 lane variants для каждого patch. Общая boundary меняется — выбрать affected consumers и переиспользовать один точный shared witness. Неприменимое обосновать. Отсутствующий backend/owner не заменять моделью ожидаемого ответа.

## 10. Что сознательно НЕ рекомендовано

- Не вводить новый universal policy/ontology/discovery/authority framework поверх existing owners.
- Не запрещать новую generic semantics под лозунгом literal zero-new-code.
- Не заявлять empirics из synthetic calculator, coverage из nominal label, authority из registry presence или currentness из одинаковых bytes.
- Не менять зависимости на newest ради отчёта; Python3.14, locked numeric packages, отдельный selected DoWhy worker и Node22 profiles — реальные ограничения.
- Не считать limited HARD training/spill/provider coverage defect без выбранного более сильного contract.
- Не добавлять mandatory index при трёх governed rows и не рисовать измеренный SLO по source complexity.
- Не заменять independent oracle второй обёрткой над тем же tested evaluator.
- Не делать full-platform/native/cloud запуск условием каждого небольшого ремонта.

## 11. Ограничения этого review и финальная диспозиция

Полностью прочитаны 12 lane overviews, 12 shared contracts/38 scenarios, четыре practical stories, общие правила/решения и ключевые первичные architecture directions. Source owner/code/test чтение выборочное, точные ranges указаны. Не заявлено повторное полное чтение 127 packets или всех 20 architecture documents: они распределены между reviewers. Реальная работоспособность, performance и empirical quality здесь **не измерены**.

**Диспозиция:** retain архитектурный каркас и текущие сильные guards/positive tests; targeted revision процедуры X03; conditional qualification actual discovery/usefulness; measured-cost decision вместо преждевременной оптимизации; конкретные X04 witnesses для уже известных conditional gaps. Root должен объединить совпадающий X03 вывод и локальные packet findings в одну непротиворечивую редакцию, без дублированных test frameworks и искусственного увеличения обязательного scope.
