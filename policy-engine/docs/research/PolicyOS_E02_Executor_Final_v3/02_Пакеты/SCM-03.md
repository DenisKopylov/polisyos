# SCM-03 — Канонический manual query-plan и устойчивые совместные posterior replicas

**Исполнительская спецификация; финальная QA комплекта ещё ожидается.**
**LANE-05 · CP5 · B224, B225.** Основание `20d9009be21097bfbdc38a546a15cc60213b8ace`. Реализация документом не выполнена; все будущие проверки **NOT_RUN**. Именных исполнителя/reviewer назначает проект.

## 1. Практическая цель и область

Закрыть manual graph admission и order-sensitive posterior streams, сохранив уже работающие perfect surgery, active pruning и настоящий stochastic law.

**Тип работы:** Bounded graph-consumer repair C59-R01; low reproducibility repair C59-R02; native/performance qualification. Не новая универсальная graph/sampling платформа.

[Аудит](../05_Основания/Аудит/02_Пакеты/SCM-03.md) · [остатки](../05_Основания/Аудит/01_Реестры/C59_остатки.json) · [исходная карточка](../05_Основания/Аудит/05_Источники/SCM-03_исходные_строки.txt) · [источники](../05_Основания/Аудит/05_Источники/C59_источники.json) · [трассировка](../04_Трассировка/SCM-03.json). Полные диагностические scripts/logs остаются в отдельно доставленном ZIP фазы 1. Действуют [общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## 2. Исходные обязанности и сохранение

B224 perfect replacement/active plan/per-node streams уже реализованы, но manual unresolved marks и joint posterior order остаются. B225 strict law parser/conditional tail sampler уже исправлены. A07 сохраняет factual/joint-law dependencies и sharedU; исходные predecessors SCM-02, GRF-01, GRF-02.

- `preserve:0568`: Perfect replacement before natural sampler → REQ-SCM-03-04; TEST-SCM-03-05.
- `preserve:0569`: Active/factual closure and full-trace opt-in → REQ-SCM-03-04; TEST-SCM-03-05.
- `preserve:0570`: Immutable graph/per-node logical streams and mutant control → REQ-SCM-03-03, REQ-SCM-03-04; TEST-SCM-03-03, TEST-SCM-03-04, TEST-SCM-03-05.
- `preserve:0571`: One stochastic-law parse, strict failure without hidden atomic alternative → REQ-SCM-03-05; TEST-SCM-03-06.
- `preserve:0572`: Actual conditional tail sampler and separate clipping semantics → REQ-SCM-03-05; TEST-SCM-03-06.

## 3. Disposition полного остатка

| ID | Действие / причина | REQ / общий владелец |
|---|---|---|
| `C59-R01` | fix: Canonical existing graph owner применяется к manual consumer, selected producer не обвиняется. | REQ-SCM-03-01, REQ-SCM-03-02 |
| `C59-R02` | fix: Canonical posterior coordinate mapping, covariance сохранена; low replay issue не numerical bias. | REQ-SCM-03-03 |
| `C59-G01` | qualify: Actual custody и representative measurement, bounded counters не native app acceptance. | REQ-SCM-03-04, REQ-SCM-03-05, REQ-SCM-03-06 |
| `C59-G02` | shared: Соседние conditional-law repairs и scientific/refit boundaries явно распределены. | REQ-SCM-03-04, REQ-SCM-03-05, REQ-SCM-03-07; SCM-01/SCM-02 |

Все source-registry remaining также связаны: `remaining:0353`, `remaining:0354`, `remaining:0355`, `remaining:0356`. Подробная причина и REQ для каждой строки — в companion JSON; повторная запись не считается новым независимым дефектом.

## 4. Нормативный контракт

### REQ-SCM-03-01
Каждый static SCM query entry, включая manual/no-source-disposition, планируется только по заново проверенному directed DAG или canonical projection существующего owner. Raw src/dst при endpoint marks не служат causal orientation. Unresolved PAG/temporal graph не получает static numerical success; корректные manual DAG и known-direction equivalent spellings остаются полезными.
Источник: B224; C59-R01. Проверки: TEST-SCM-03-01, TEST-SCM-03-02.

### REQ-SCM-03-02
Projected graph, mechanism parents и source/disposition связываются согласованно до traversal. Если projection требует отсутствующих latent mechanisms или family semantics, вернуть точный unsupported capability, не придумать mechanisms. Не мутировать source graph и не ослаблять selected fit guard.
Источник: B224; C59-R01. Проверки: TEST-SCM-03-01, TEST-SCM-03-02, TEST-SCM-03-07.

### REQ-SCM-03-03
Joint Gaussian posterior имеет canonical logical coordinate order и stream identity, не зависящие от permutation equivalent nodes/edges/mechanism storage. В одном accepted runtime/backend одинаковые effective SCM/query/seed дают соответствующие replicas в declared tolerance; joint covariance и shared-U сохраняются. Это reproducibility contract, не утверждение о ранее biased marginals.
Источник: B224; C59-R02. Проверки: TEST-SCM-03-03, TEST-SCM-03-04.

### REQ-SCM-03-04
ATOMIC/STOCHASTIC replacement происходит до natural mechanism; SHIFTED/TRUNCATED сохраняют нужное natural value. Active scope включает все необходимые arm/factual/joint-law dependencies и full-trace лишь по explicit запросу. Immutable graph и per-node streams сохраняются при irrelevant insertion/pruning.
Источник: B224; C59-G01, C59-G02. Проверки: TEST-SCM-03-04, TEST-SCM-03-05.

### REQ-SCM-03-05
Supported stochastic law normal/uniform/truncnorm разрешается один раз до draws, проверяет finite args/arity/positive scale и исполняет исходный тип политики. Malformed/unsupported law отказывает даже при fallback_treatment_value, не меняется на atomic. Conditional truncnorm и TRUNCATED clipping различаются; degenerate declared interval имеет собственный явный смысл.
Источник: B225; C59-G01, C59-G02. Проверки: TEST-SCM-03-06.

### REQ-SCM-03-06
Native registered query→persisted result→fresh Scientist reader сохраняет graph/law/target/comparator/seed profile и whole-output bindings. Работа с counters не равна доказанному wall-time/RSS speedup; performance claim требует representative measured workload и denominators.
Источник: B224, B225; C59-G01. Проверки: TEST-SCM-03-07, TEST-SCM-03-08.

### REQ-SCM-03-07
Новый compatible graph/law profile подключается через existing graph projection и law owner, не special-case по имени узла. Неизвестные law/empirical authority/estimator coverage остаются ограничениями; C57 twin и C58 posterior/conditional-law repairs входят в shared closeout. Refit qualification принадлежит SCM-02 и не засчитывается tail test.
Источник: B224, B225; C59-G02. Проверки: TEST-SCM-03-02, TEST-SCM-03-06, TEST-SCM-03-07, TEST-SCM-03-08.

## 5. Конкретное техническое решение

**Admission.** Сформировать один validated static query view до `_parents_by_node/_topological_order`, используя текущие `project_graph_to_dag`, typed disposition и `graph_for_analysis`. Для manual DAG — strict canonical revalidation; для known-direction non-DAG storage — canonical projection и consistency с mechanism parents. Не изменять оригинальный SCM/source in place: prepared view относится к exact admitted graph/mechanism identity. Неразрешённый PAG, temporal edge или projection с отсутствующим latent mechanism остаются explicit unsupported, а не raw adjacency. Selected fit уже имеет guard; ремонт на manual consumer boundary не дублирует fitter.

**Posterior replicas.** При подготовке posterior строить affine matrix в canonical topological order (tie-break по stable variable identity, parent accumulation также canonical), затем сохранять явный canonical coordinate tuple. Factor/draw/map используют один tuple. Это локальное свойство posterior preparation; не обязательно менять внешний `_topological_order` только ради сортировки: существующий test намеренно демонстрирует разные sibling orders и полезен как distinguishing input. Shared factor согласовать со scale-aware repair SCM-02. Stable namespace/label existing `_LogicalStreamFactory` сохранить; не подменять joint vector набором независимых noises. Within fixed runtime canonical matrix обеспечивает воспроизводимость; cross-BLAS/version bitwise guarantee отдельно не обещать.

**Plan/law reuse.** Perfect replacement и parse-once уже правильны, сохранить counters/tripwires. Если вводится кэш prepared plan, ключ включает canonical graph/mechanisms, query type/arms, evidence dependency pattern и full_trace semantics; кэш по одному outcome недопустим. Не создавать cache, если текущая query-local подготовка достаточна: измеренный дорогой repeat — prerequisite оптимизации. Truncnorm остаётся actual conditional sampler со standardized a,b; clipping — другой intervention type.

### Текущие owners и источники

- [policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py:52–146](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L52-L146)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py:277–437](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L277-L437)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py:893–1015](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L893-L1015)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py:1238–1489](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L1238-L1489)
- [policy-engine/src/polisyos/ir/analytics/structural_causal_model.py:208–242](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/structural_causal_model.py#L208-L242)
- [policy-engine/src/polisyos/ir/analytics/causal_graph.py:340–390](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L340-L390)
- [policy-engine/src/polisyos/ir/analytics/causal_graph.py:1078–1177](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L1078-L1177)
- [policy-engine/tests/unit/remediation/test_scm_03.py:190–309](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_scm_03.py#L190-L309)

## 6. Проверки: setup → действие → oracle

TEST-ID обозначает требуемую проверку, не существующий одноимённый pytest test. Расширять указанные действительные места, не дублировать suites.

### TEST-SCM-03-01 · native manual admission distinguishing regression
**NOT_RUN. REQ:** REQ-SCM-03-01, REQ-SCM-03-02.
**Setup:** Manual PAG X o→Y с mechanisms, querydoX2; knownY→X в двух spellings (X,Y,arrow,tail) и(Y,X,tail,arrow), Y5,X2Y, querydoY2→X.
**Действие:** Public query route выполняет canonical admission/projector перед active plan; positive plain manual DAG control.
**Oracle:** Unresolved PAG не возвращает success7; known equivalent directions дают X4 в обеих записях, не KeyError. Полный original source сохранён, derived DAG/disposition согласованы с mechanisms.
**Место:** `gcm_query.py public pure_step; ir/analytics/causal_graph.py::project_graph_to_dag/graph_for_analysis`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-SCM-03-02 · native supported-boundary control
**NOT_RUN. REQ:** REQ-SCM-03-01, REQ-SCM-03-02, REQ-SCM-03-07.
**Setup:** Manual temporal edge, cycle, stale/forged disposition, graph projection с introduced latent node без mechanism; valid ordinary manual DAG.
**Действие:** Admit before topological traversal and execute valid case.
**Oracle:** Temporal/cycle/unresolved/missing required mechanism получают адресный refusal до sampling, не raw orientation или тайный latent law. Valid manual model работает; selected source-bound fit protections не ослаблены.
**Место:** `structural_causal_model.py; GRF-03 canonical projection owner`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-SCM-03-03 · native posterior permutation regression
**NOT_RUN. REQ:** REQ-SCM-03-03.
**Setup:** Existing _b224_reordered_active_models, same seed31,n512; conditionsY4 иB1, controlsR1 иB1,C2; permutation edges/nodes/mechanism storage.
**Действие:** Actual counterfactual GCM posterior simulation и shared draw owner; map samples по canonical variable labels.
**Oracle:** Все corresponding replicas совпадают в фиксированной runtime tolerance(atol1e-12/rtol1e-12 для fixture), включая ранее различавшиеся cases. Mean/cov аналитически те же. Independent per-node replacement вместо correlated vector должен провалить covariance/sharedU control.
**Место:** `tests/unit/remediation/test_scm_03.py; gcm_query.py::_linear_gaussian_posterior/_LogicalStreamFactory`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-SCM-03-04 · native stream/pruning removal controls
**NOT_RUN. REQ:** REQ-SCM-03-03, REQ-SCM-03-04.
**Setup:** Existing interventional sibling reorder и irrelevant root insertion; explicit generator input; posterior correlated control из SCM-02.
**Действие:** Выполнить current per-node stream tests и mutant shared mutable RNG control; измерить consumption root token explicit generator.
**Oracle:** Relevant per-node replicas инвариантны reorder/pruning; mutant обнаружен. Root entropy берётся фиксированным token, не меняется от размера плана. Joint posterior сохраняет off-diagonal covariance/sharedU, не превращается в independent noises.
**Место:** `tests/unit/remediation/test_scm_03.py:190–309`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-SCM-03-05 · native replacement/counters
**NOT_RUN. REQ:** REQ-SCM-03-04.
**Setup:** X,Y плюс20 irrelevant roots,10draws; broken naturalX tripwire; U→X→Y с missingU; shift natural5+2 и factual ancestor case.
**Действие:** Execute active и full_trace routes; instrument actual node calls/retained arrays, snapshot graph before/after.
**Oracle:** PerfectdoX2→Y7 без naturalX; active10calls/20values vs full_trace210calls/220values на этом fixture, Y replicas одинаковы. Shift требует natural5→7 и нужныйU; factual/joint-law dependencies не удалены. Source graph неизменён. Это counters, не benchmark speedup.
**Место:** `tests/unit/remediation/test_scm_03.py; SCM-01/02 dependency controls`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-SCM-03-06 · native SciPy law oracle
**NOT_RUN. REQ:** REQ-SCM-03-05, REQ-SCM-03-07.
**Setup:** truncnorm(0,1,8,9),n2048,seed23; normal/uniform positive; typo/emptyarg/zero-negative scale/NaN с fallback7; explicit degenerate[8,8], separate clipping.
**Действие:** Count resolver calls; sample actual SciPy, compare independent quadrature of exp(-(x²−64)/2) on[8,9]; repeat seed.
**Oracle:** Parser один раз; nondegenerate tail values строго внутри(8,9), разнообразны; mean8.12118899 within6sqrt(.01414854/2048), variance согласована в заранее установленном finite tolerance. Invalid law отказывает, не десять7; clipped natural0→8 и declared degenerate8 отдельно valid. Same-runtime seeded repeat сохраняется.
**Место:** `tests/unit/remediation/test_scm_03.py; _resolve_stochastic_distribution/_sample_stochastic_distribution`.
**Doubles:** Real SciPy sampler не подменять готовыми numbers. Quadrature oracle не вызывает тот же truncnorm.rvs.

### TEST-SCM-03-07 · native E02-I05-C source→query→reader
**NOT_RUN. REQ:** REQ-SCM-03-02, REQ-SCM-03-06, REQ-SCM-03-07.
**Setup:** Actual selected static fitted SCM плюс manual admitted DAG fixture, declared stochastic query/contrast, real CAS/profile-selected fresh reader.
**Действие:** Registry/dispatcher→whole canonical output→Scientist reconciliation; mutate source, projection, law, arms, metadata or profile with valid new payload serialization.
**Oracle:** Valid numerical candidate достигает consumer; semantic substitutions refused относительно source/request, не только peer equality. Conservative envelope/limits сохранены, unknown law не upgraded. C57/C58 repairs подтверждены тем же agreed revision.
**Место:** `scientist/nodes/builtins/causal/run_causal_queries.py; actual selected source-bound test_gcm_backend_contract.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-SCM-03-08 · bounded performance/scientific qualification
**NOT_RUN. REQ:** REQ-SCM-03-06, REQ-SCM-03-07.
**Setup:** Один заранее объявленный representative graph/query corpus с active/full_trace variants; pinned environment, n_samples, warmup/repeats/RSS method.
**Действие:** Если нужен performance claim, измерить wall-time/RSS и numerical equivalence отдельно; составить supported law/graph/scientific scope table.
**Oracle:** Нет обещания общего speedup из10/210 counters. Regression/overhead и denominators видимы. Tail/law correctness не считается refit CI/empirical policy authority; source-bound refit evidence ссылается на SCM-02, не дублируется.
**Место:** `Actual query application owner; E02-I05-C`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### Запуск: адаптируемый шаблон, не выполненная команда

Из `policy-engine/` в поддержанной Python3.14 среде с закреплёнными зависимостями. Этот документ не разрешает автоматические installs; отсутствующая dependency означает BLOCKED конкретной проверки.

```bash
python -V
python -m pytest -q tests/unit/remediation/test_scm_03.py tests/unit/remediation/test_scm_01.py tests/unit/remediation/test_scm_02.py
# Actual selected worker/query/Scientist qualification E02-I05-C; performance job только при конкретном claim.
```

Фиксировать профиль/backend, inputs/seed/hash, deciding output и exit. Ruff и затронутые architecture/import checks выбирать по фактическому patch; native slot согласовать, полный suite на каждый пакет не копировать.

## 7. Общая интеграция и ownership

Переиспользовать **E02-I05-C**: [канонический контракт LANE-05](../03_Интеграция/LANE-05.md). Одно свидетельство связывается с конкретными вариантами и REQ; не считается многими независимыми подтверждениями.

SCM-03 — единственный writer graph admission/common closure/prepared-plan API и canonical stream coordinates. SCM-02 — единственный writer conditional-row/PSD и owner refit qualification; SCM-01 — twin consumer и native selected fit→query acceptance. Правки общего gcm_query.py передаются последовательно, не конкурентно. IR projection owner GRF-03 переиспользуется без parallel graph parser. Shared native suite один E02-I05-C.

- **SCM-02:** Оригинальный predecessor: posterior factor/joint conditioning; canonical coordinate fix согласован с numerical change.
- **GRF-01:** Оригинальный predecessor: intervention surgery и graph semantics.
- **GRF-02:** Оригинальный predecessor: immutable canonical identity/prepared adjacency.
- **GRF-03:** Existing canonical projection/disposition reuse, static/temporal boundary.
- **SCM-01:** Twin query-specific closure использует тот же supported-plan semantics, не отдельный parser.

## 8. Совместимость, миграция и возврат

Manual valid DAG preserved; unresolved/raw reverse behavior intentional correction. New canonical posterior mapping меняет ошибочно representation-sensitive replicas, но не объявляет старый marginal law biased. Зафиксировать replay profile/version и old/new seed mapping через existing provenance, historical bytes не переписывать. Strong cross-version reproducibility не заявлять без отдельного pinned backend evidence. Rollback не возвращает silent atomic fallback.

## 9. Free-grow и обоснованные границы

- [universal-policy-design-target-architecture-and-gap.md — D0](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): Общий canonical graph/plan и law owner позволяют новым compatible inputs работать без новых веток; positive manual DAG сохраняется рядом с refusal.
- [policy-design-execution-topology.md — Applicability versus semantic judgment](../05_Основания/Архитектура/policy-design-execution-topology.md): Исполняется именно предложенный и admitted law; LLM proposal не источник empirical authority, но useful conditional calculation не блокируется blanket.

## 10. Конечные решения и сдача

### DEC-SCM-03-REPLAY
**Вопрос:** Как закрепить исправленную posterior coordinate policy в existing replay provenance?
**Кто решает:** SCM-03 — canonical stream coordinates writer; SCM-02 numerical reviewer.
**Конечное действие/выход:** Проверить current schema/stream version fields и downstream readers; выбрать существующий computation-profile marker или минимальное versioned extension. Зафиксировать same-runtime tolerance, changed draws и unchanged target law, genuine historical bytes не менять.
**До решения:** Canonical within accepted runtime; не обещать equivalence исторических draws или cross-version BLAS.

Сдать base/head и patch, exact REQ→TEST→shared variant, исходные входы и их идентичности, actual команды/exit/log, независимые численные/семантические oracles, positive/negative/removal controls, сохранённые инварианты и открытые решения. Source-only, fixture, native и scientific qualification отражать отдельно. Не повышать partial/NOT_RUN до PASS; квалифицированный локальный механизм не является автоматической готовностью всей политики.
