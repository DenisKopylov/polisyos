# GRF-03 — известные направления и явная temporal/partial семантика
## C50 · 1 ноября 2026 года

**Порядок:** 50/127, LANE-05. **Исходные IDs:** B214, B218. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит. Этот C50 получен заново после внешнего сохранения восстановленного C49; утраченный прежний C50 не является доказательством.

## Решение

Исходное semantic flipping не найдено в текущем owner: **PAG X←Y становится Y→X**, с сохранением original endpoints/marks. Unresolved CPDAG triangle получает точный отказ, а fully oriented directed cycle не проходит создание настоящего DAG. Compact temporal graph сохраняет lag; положительная autoregression разрешена, simultaneous loop/cycle запрещены. Static fit и sampling отказывают **до** численного исполнения вместо молчаливого отбрасывания лагов.

**20 bounded MATCH, 9 неизменённых test bodies PASS изолированно; новых подтверждённых R нет.** Среди исполнений — actual extracted native-hybrid fit body с настоящими graph/SCM DTO и source/projection binding. Это не native package/DoWhy/CAS acceptance. Поддержанная среда и общая temporal/partial-graph capability остаются квалификационными пробелами, а не объявляются автоматически реализованными или отсутствующими.

## 1. Матрица исходных ID

| ID | Исходная проблема | Проверенное текущее поведение | Остаток |
|---|---|---|---|
| B214 | Known reverse edge менял причинное направление; unresolved triangle получал DAG-label без validation | Reverse endpoints переставляются; original marks сохраняются; разрешённый результат создаётся полноценным `CausalGraphModel(DAG, ...)`; unresolved/cyclic inputs отказывают; typed hybrid consumer сохраняет source и disposition | C50-G01: native lifecycle; G03: qualified partial-family inference |
| B218 | Lag терялся в DOT; positive self-lag отвергался; static helpers/fit расходились в чтении temporal graph | DOT и DTO различают lag1/lag2; positive directed self-lag допустим; zero-lag cycle запрещён; static adjacency, fit и sampling явно отказывают compact temporal input | C50-G01: поддержанная среда; G02: реальный data/time/horizon adapter |

Полная исходная карточка, строки 6129–6220, прочитана. Полная поддержка всех PAG/temporal families не превращена в предварительное условие локального static ремонта. Неудобные edges не удалялись; DAG validation не отключалась.

## 2. Canonical owner и содержательная связь с потребителем

`_graph_projection.pag_to_dag_projection` теперь лишь compatibility alias канонического IR `project_graph_to_dag`. Owner сначала восстанавливает настоящий canonical graph; поддержанный профиль ограничен явно. Known reversed edge получает swapped endpoints, TAIL→ARROW и metadata с исходными endpoints/marks. ADMG bidirected edge превращается в общий latent parent с именем, не конфликтующим с существующими nodes. Результат создаётся обычным валидируемым DAG constructor, а не `model_copy(graph_type=DAG)` поверх произвольного графа. [S03](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/_graph_projection.py) [S01:1054–1182](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L1054-L1182)

Actual `HybridSCMFit.pure_step` сначала проверяет graph content и temporal restriction. Затем ветви различаются:

- Default **selected DoWhy GCM** требует fully observed declared static DAG; это не обещание автоматического выбора PAG completion.
- Явно выбранный **native_hybrid** вызывает canonical projector для non-DAG input и сохраняет `source_graph`, `source_graph_ref` и content-bound projection disposition вместе с mechanisms в `StructuralCausalModelSpec`.

SCM DTO проверяет совместное присутствие source/disposition и заново сверяет canonical projection через `graph_for_analysis`. Поэтому metadata — не единственная связь с producer. [S04:460–508](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py#L460-L508) [S04:610–827](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py#L610-L827) [S07:189–227](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/structural_causal_model.py#L189-L227)

**P15 — не только graph fixture:** exact SCMFitData class исполняет реальные Pydantic validators; actual hybrid method и OLS helper получают синтетические X=2Y rows и PAG X←Y. Возвращён настоящий SCM DTO, X имеет parent Y и coefficient≈2, source graph/ref и projected disposition сохранены. Determinism metadata enum здесь fixture, class bootstrap пропущен; selected backend tripwire не исполнялся. Это ограниченный producer→typed consumer witness, **не эмпирическое доказательство X←Y и не native installed fit**.

**P16/P17:** настоящий content-bound disposition допускает canonical Y→X result и отвергает подставленный X→Y. Persisted CAS/report/query lifecycle не исполнен и остаётся G01.

## 3. Known direction не смешивается с неизвестной orientation

- **P01/P02:** reversed source нормализован; original marks, evidence refs и произвольная metadata сохранены; исходный graph не изменён.
- **P03:** unresolved CPDAG triangle получает `partial_graph_endpoint_profile_not_admitted`, а не произвольный DAG.
- **P04:** fully oriented циклический PAG проходит local endpoint profile, но настоящий DAG constructor отказывает по acyclicity. Это сохранённая проверка, а не обход ради результата.
- **P05:** при уже существующем U_0 latent common parent назван U_1 и соединён с обоими endpoint; edge basis сохранён.
- **P06:** корректный static DAG остаётся равным по содержимому detached snapshot.

Семь существующих GRF tests исполнены неизменёнными. Один перебирает **90 combinations**: 5 graph kinds × 9 endpoint pairs × 2 storage directions, а также проверяет refusal validator-bypassed copies. Это конечный admission denominator; он не доказывает soundness/completeness inference на произвольном PAG. [S08:1–219](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_grf_03.py#L1-L219)

Static ID entry вызывает `_validate_static_id_graph` до своих shortcuts. Partial-tag admission остаётся отдельным от explicit resolved DAG projection; наличие поздней ветки или имени PAG в ID source не объявляется рабочей общей partial-family capability. [S02:255–305](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py#L255-L305) [S11:545–578](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/id_engine/core.py#L545-L578)

## 4. Temporal input сохранён, но static execution не притворяется temporal

DTO допускает self-edge только как положительное lagged directed relation. DAG cycle check касается contemporaneous edges; взаимные положительные лаги не считаются simultaneous cycle. DOT содержит lag/temporal attributes, поэтому lossless transport уже различает lag1 и lag2. **Но атрибут DOT сам по себе не заставляет любой сторонний backend учитывать время.** [S01:610–651](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L610-L651) [S01:722–743](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L722-L743)

**P07–P12:** actual round-trip сохраняет lag1/lag2; positive autoregression принимается; zero-lag self-loop и simultaneous cycle отклоняются. Reciprocal lag1 graph сохраняется при DAG identity projection без молчаливой expansion/удаления edges, но static adjacency отказывает с указанием lag. Identity здесь означает сохранение compact content, не разрешение подать его любому static consumer.

**P14:** для actual SCMFitData с temporal graph full extracted fit method отказывает при обоих `fit_backend` значениях, не вызвав backend. **P18:** actual `_simulate_samples` первой операцией вызывает `_topological_order` и отказывает до чтения query fields или sample generation. Query/spec wrappers в этом конкретном early-refusal control структурные, graph DTO настоящий. **P19:** статический fitted Y→X graph получает корректный порядок Y,X. [S04:610–626](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py#L610-L626) [S05:112–141](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L112-L141) [S05:1315–1340](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L1315-L1340)

**P13:** ручное развёртывание двух переменных на четыре времени даёт 8 nodes, 6 time-advancing edges и принимается настоящим DAG DTO. Это только finite mathematical control. Он **не выдаётся за production temporal adapter**, не устанавливает соответствие фактическим observations, initial conditions или horizon. Другие temporal subsystems в этой карточке не оценены и не объявлены отсутствующими.

## 5. Сохраняемый результат и открытые границы

**C50-G01 — native qualification.** Поддержанная среда Python 3.14/Pydantic ещё нужна. Pytest отсутствует; обычный public fit import останавливается на Python 3.14 exception syntax в uncertainty.py под Python 3.12. DoWhy worker, execution service, CAS round-trip и full query envelope не запускались. Два existing GCM-fit bodies дополнительно выполнены с объявленными seams; всего 9 isolated bodies, не pytest session.

**C50-G02 — реальная temporal способность.** Для требуемого пользовательского пути отдельно нужны time coordinates, lag convention, horizon, initial conditions и data-time binding. Корректный static refusal — настоящий ремонт исходного искажения, но не готовый temporal answer. Следует связывать существующий подходящий consumer, а не вводить новый универсальный temporal subsystem автоматически.

**C50-G03 — partial-family и scientific authority.** Нормализация известного направления и ограниченное latent representation полезны; неизвестные marks нельзя превращать в arbitrary DAG. Сохранить source graph, typed limitation и допустимый conditional result. LLM может предлагать структуру; ни этот finite oracle, ни synthetic OLS не превращают её в подтверждённую causal world model. Отсутствие универсального deterministic inventor не является дефектом B214/B218.

[Результаты](../04_Проверки/C50_GRF03/bounded_diagnostics.json) · [Команды](../04_Проверки/C50_GRF03/commands.json) · [Границы](../04_Проверки/C50_GRF03/native_verification.json) · [Источники](../05_Источники/C50_источники.json) · [Остатки](../01_Реестры/C50_остатки.json).

**50/127 пакетов рассмотрены ограниченно; 120 уникальных B/LA частично оценены. Следующий — API-01. Полного закрытия нет.**
