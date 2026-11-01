# GRF-03 — Известная orientation без flip и явная temporal/partial capability

**Исполнительская спецификация; финальная QA комплекта ещё ожидается.**
**LANE-05 · CP5 · B214, B218.** Основание `20d9009be21097bfbdc38a546a15cc60213b8ace`. Реализация документом не выполнена; все будущие проверки **NOT_RUN**. Именных исполнителя/reviewer назначает проект.

## 1. Практическая цель и область

Квалифицировать уже правильный canonical projection и source-bound SCM lifecycle. Для реально требуемого temporal/partial запроса выбрать существующий подходящий consumer либо минимальный явный adapter с data/time binding, не превращать честный static refusal в ложную полноту.

**Тип работы:** Preserve/native qualification исходных repairs; ограниченное решение capability по temporal и unresolved graph family. Новых подтверждённых R в C50 нет.

[Аудит](../05_Основания/Аудит/02_Пакеты/GRF-03.md) · [остатки](../05_Основания/Аудит/01_Реестры/C50_остатки.json) · [исходная карточка](../05_Основания/Аудит/05_Источники/GRF-03_исходные_строки.txt) · [источники](../05_Основания/Аудит/05_Источники/C50_источники.json) · [трассировка](../04_Трассировка/GRF-03.json). Полные диагностические scripts/logs остаются в отдельно доставленном ZIP фазы 1. Действуют [общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## 2. Исходные обязанности и сохранение

B214 reversed known edge уже нормализуется перестановкой endpoints, DAG создаётся через validation, partial/cyclic graph не переименовывается. B218 lag сохраняется в DTO/DOT, positive self-lag разрешён, zero-lag cycles запрещены, static fit/query отказывают до backend. General PAG/temporal support не предварительное условие локального static ремонта; но нужный положительный temporal путь остаётся отдельной работой, не одним pytest.

- `preserve:0543`: Canonical direction normalization with original marks → REQ-GRF-03-01; TEST-GRF-03-01.
- `preserve:0544`: Validated DAG construction и typed partial-profile refusal → REQ-GRF-03-01, REQ-GRF-03-05; TEST-GRF-03-01, TEST-GRF-03-02.
- `preserve:0545`: Latent common-parent construction с collision-free names → REQ-GRF-03-01; TEST-GRF-03-01.
- `preserve:0546`: Positive lagged self-edge, lag-preserving serialization, zero-lag cycle guard → REQ-GRF-03-03; TEST-GRF-03-05.
- `preserve:0547`: Early static fit/query admission и content-bound source/projection → REQ-GRF-03-02, REQ-GRF-03-03; TEST-GRF-03-03, TEST-GRF-03-04, TEST-GRF-03-05.

## 3. Disposition полного остатка

| ID | Действие / причина | REQ / общий владелец |
|---|---|---|
| `C50-G01` | qualify: Native fit/query/source/CAS и separate selected worker. | REQ-GRF-03-01, REQ-GRF-03-02, REQ-GRF-03-03, REQ-GRF-03-07 |
| `C50-G02` | capability: Один реально полезный temporal route/data-time binding; static refusal alone недостаточен для заявленного temporal use. | REQ-GRF-03-03, REQ-GRF-03-04, REQ-GRF-03-06 |
| `C50-G03` | capability: Qualified family semantics либо explicit conditional hypothesis/route limitation, не arbitrary DAG. | REQ-GRF-03-01, REQ-GRF-03-05, REQ-GRF-03-06 |

Все source-registry remaining также связаны: `remaining:0337`, `remaining:0338`, `remaining:0339`. Подробная причина и REQ для каждой строки — в companion JSON; повторная запись не считается новым независимым дефектом.

## 4. Нормативный контракт

### REQ-GRF-03-01
Canonical project_graph_to_dag сохраняет known causal direction при reverse storage, original endpoints/marks/metadata/evidence и immutable source. Корректный DAG остаётся detached content-equivalent; ADMG bidirected даёт общий latent parent без name collision. Unresolved marks/cyclic result не получают arbitrary DAG label и не лечатся удалением неудобных edges.
Источник: B214; C50-G01, C50-G03. Проверки: TEST-GRF-03-01, TEST-GRF-03-02.

### REQ-GRF-03-02
Native source→projection→native_hybrid fit→SCM artifact→CAS fresh read→query сохраняет content-bound source_graph/source_ref/disposition. Подставленная reverse direction либо foreign graph не проходит graph_for_analysis. Default selected DoWhy GCM остаётся отдельным fully observed declared static DAG profile; hybrid test не заменяет worker acceptance.
Источник: B214, B218; C50-G01. Проверки: TEST-GRF-03-03, TEST-GRF-03-04.

### REQ-GRF-03-03
Temporal compact content различает lag1/lag2 и positive directed self-lag после serialization/export; simultaneous cycles/self-loop остаются запрещены. Static adjacency/fit/query отказывают до numerical backend/sampling, пока явный temporal adapter не выполнен. DOT lag attribute сам по себе не разрешает static backend игнорировать время.
Источник: B218; C50-G01, C50-G02. Проверки: TEST-GRF-03-05.

### REQ-GRF-03-04
Для одного выбранного реально нужного temporal use case квалифицировать existing temporal consumer либо finite expansion: координата(variable,time), знак/единица lag, horizon, initial/boundary conditions и source observation/time binding заданы до вычисления. Expansion строит только необходимую конечную область запроса с её предками, сохраняет исходный graph/ref и mapping, не отбрасывает необеспеченные начальные значения как нули.
Источник: B218; C50-G02. Проверки: TEST-GRF-03-06, TEST-GRF-03-07.

### REQ-GRF-03-05
Unresolved PAG/CPDAG сохраняется как исследовательский source и конкретная limitation static route. Если нужен ответ по partial family, выбранный квалифицированный owner должен обосновать family semantics/допустимые completions и область invariant claim; single arbitrary completion не выдаётся за весь PAG. При отсутствии такого owner допустим полезный conditional result по явно выбранной гипотезе, не false identified result.
Источник: B214; C50-G03. Проверки: TEST-GRF-03-02, TEST-GRF-03-08.

### REQ-GRF-03-06
Новый совместимый temporal graph или known-direction hypothesis подключается тем же declared adapter/contract без case-name веток. LLM может предлагать структуру, но synthetic coefficient/finite expansion не устанавливают empirical causality. Scope/assumptions у fresh consumer остаются видимыми, unsupported claim не уничтожает lawful static/descriptive результат.
Источник: B214, B218; C50-G02, C50-G03. Проверки: TEST-GRF-03-03, TEST-GRF-03-06, TEST-GRF-03-08.

### REQ-GRF-03-07
Native tests/public imports используют поддержанный Python/dependency profile и actual CAS/selected references. Parent namespace shells, AST extraction и ручной8-node graph из аудита не считаются выполненным temporal adapter либо default DoWhy worker. Product diff для уже проходящих static repairs не требуется.
Источник: B214, B218; C50-G01. Проверки: TEST-GRF-03-01, TEST-GRF-03-03, TEST-GRF-03-04, TEST-GRF-03-05.

## 5. Конкретное техническое решение

Static normalization уже канонически принадлежит IR `project_graph_to_dag`; `_graph_projection` — alias, не второй algorithm. Сохранить перестановку endpoints для ARROW/TAIL, original marks, collision-free latent parents и настоящий DAG constructor. `StructuralCausalModelSpec` source+disposition проверяется через `graph_for_analysis`; native lifecycle должен сохранить эту связь до query, а не ограничиться DTO shape.

**Temporal scope:** сначала finite census actual temporal consumers/model contracts, без предположения, что вся система их лишена. Если выбранный consumer уже понимает compact lag, квалифицировать его data/time boundary. Если для нужного запроса есть только static computation, минимальный adapter у существующего graph/model owner создаёт finite `(variable,time)` DAG: edge src→dst lagL становится src(t-L)→dst(t) только в declared horizon plus required ancestor history; lag0 проходит contemporaneous cycle validation. Имена кодируются collision-safe, map original variable/time сохраняется. Initial/boundary values имеют source refs/условные assumptions; неизвестное не подставляется0. Данные join по exact time/variable, не по позиции несогласованных массивов. Static consumers получают уже проверенный finite profile и binding, а compact temporal input продолжает early-refuse. Не строить новый универсальный temporal subsystem.

**Partial graph:** canonical known-direction projection — не completion-family inference. Для реально требуемого unresolved query finite census находит подходящий existing owner/algorithm и его supported family; иначе оставить source+limitation и явную conditional hypothesis. Если несколько hypotheses сравниваются, результат говорит per-hypothesis/invariant только по проверенной области, а не всей PAG. Не требуется реализовать общую completeness всех PAG как условие закрытия дешёвого static repair. LLM может предложить hypothesis, но orientation не берётся из порядка хранения.

Native selected DoWhy profile и explicit native_hybrid не смешиваются. В первом actual worker нужен собственный dependency/execution evidence, во втором реальный OLS/helper и SCM source/projection. Если qualification выявляет gap в persistence, wire existing owner refs/loader; не новый evidence service.

### Текущие owners и источники

- [policy-engine/src/polisyos/ir/analytics/causal_graph.py:610–651](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L610-L651)
- [policy-engine/src/polisyos/ir/analytics/causal_graph.py:722–743](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L722-L743)
- [policy-engine/src/polisyos/ir/analytics/causal_graph.py:1054–1182](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L1054-L1182)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py:610–641](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py#L610-L641)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py:785–827](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py#L785-L827)
- [policy-engine/src/polisyos/ir/analytics/structural_causal_model.py:189–227](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/structural_causal_model.py#L189-L227)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py:112–141](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L112-L141)
- [policy-engine/tests/unit/remediation/test_grf_03.py:1–219](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_grf_03.py#L1-L219)

## 6. Проверки: setup → действие → oracle

TEST-ID обозначает требуемую проверку, не существующий одноимённый pytest test. Расширять указанные действительные места, не дублировать suites.

### TEST-GRF-03-01 · native canonical projection matrix
**NOT_RUN. REQ:** REQ-GRF-03-01, REQ-GRF-03-07.
**Setup:** Existing90-profile matrix:5graph kinds×9endpoint pairs×2storage directions; reversed PAG X←Y, valid DAG, ADMG with existingU_0.
**Действие:** Actual canonical projector/DTO validation и original dumps.
**Oracle:** Known reverse становится Y→X с original marks; same DAG content сохранён detached; bidirected parent named collision-free и связан с обоими endpoints. Metadata/evidence preserved, source unchanged. Invalid validator-bypassed copies не обходят canonical admission.
**Место:** `tests/unit/remediation/test_grf_03.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-GRF-03-02 · native unresolved/cycle controls
**NOT_RUN. REQ:** REQ-GRF-03-01, REQ-GRF-03-05.
**Setup:** Unresolved CPDAG triangle и fully oriented cyclic PAG; identical graph under input permutation; source with unresolved marks.
**Действие:** Projection/selected static ID route.
**Oracle:** Unresolved получает partial_graph_endpoint_profile_not_admitted либо exact supported refusal; cyclic rejected validated DAG constructor. Никакой model_copy(graph_type=DAG), edge deletion или arbitrary orientation. Source remains inspectable; separate conditional hypothesis не объявляется исходным family answer.
**Место:** `tests/unit/remediation/test_grf_03.py; id_engine/core.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-GRF-03-03 · native hybrid positive producer→consumer E02-I05-A/C
**NOT_RUN. REQ:** REQ-GRF-03-02, REQ-GRF-03-06, REQ-GRF-03-07.
**Setup:** PAG source X←Y, genuine SCMFitData rowsX=2Y и explicit native_hybrid; actual source graph ref/CAS.
**Действие:** Registered actual fit→persist SCM1.2→fresh canonical load→query that respects projectedY→X.
**Oracle:** Fitted X parentsY/coefficient≈2 within stated numerical tolerance; source/disposition exact, useful conditional query result reaches consumer. Это synthetic structural witness, не доказательство причинности. Foreign source/ref или substitutedX→Y отвергнуты.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_gcm_fit.py; test_gcm_query.py`.
**Doubles:** Synthetic rows допустимы; actual model validators, native_hybrid numerical fit, canonical projection/CAS/query не подменяются. Selected DoWhy worker отдельно TEST04.

### TEST-GRF-03-04 · native selected backend separation
**NOT_RUN. REQ:** REQ-GRF-03-02, REQ-GRF-03-07.
**Setup:** Declared fully observed static DAG с поддержанными mechanisms/data; actual selected DoWhy worker profile; рядом unresolved PAG и explicit hybrid case.
**Действие:** Actual default fit/query lifecycle и persisted fitted artifact.
**Oracle:** Default worker accepted only its supported DAG profile, no silent hybrid fallback; native_hybrid remains explicit distinct method. Missing worker dependency BLOCKED, не PASS от hybrid. Exact source/projection/profile survives fresh read.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_gcm_fit.py; shared E02-I05-C selected-worker fixture`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-GRF-03-05 · native lag transport/early refusal
**NOT_RUN. REQ:** REQ-GRF-03-03, REQ-GRF-03-07.
**Setup:** Lag1 vs lag2, positive autoregression, reciprocal lag1, zero-lag self-loop/cycle; both fit_backend values.
**Действие:** DTO JSON/DOT roundtrip; static adjacency/fit/query with backend tripwire.
**Oracle:** Lag values distinct, positive lag valid, contemporaneous cycles invalid. Static calls refuse before backend/sampling; tripwire0. Correct static DAG still works. DOT attribute не считается доказательством third-party temporal interpretation.
**Место:** `tests/unit/remediation/test_grf_03.py; test_gcm_fit.py; test_gcm_query.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-GRF-03-06 · native useful finite temporal route
**NOT_RUN. REQ:** REQ-GRF-03-04, REQ-GRF-03-06.
**Setup:** Selected two-variable lag1 feedback model over t0..t3, explicit initial values/source row times; second compatible model with lag2 and different variable definitions.
**Действие:** Existing temporal owner либо accepted finite adapter maps data and graph, computes requested horizon, persists mapping/result, fresh read.
**Oracle:** Первый unfolded graph8nodes/6time-advancing edges acyclic; numerical trajectory independently matches explicit recurrence по объявленным initial values. Второй case использует тот же mechanism; no case-name code. Consumer показывает time coordinates/horizon/source assumptions, не просто правильный рисунок.
**Место:** `Selected temporal owner из DEC-TEMPORAL; GRF-03 shared variant`.
**Doubles:** Synthetic recurrence — oracle механизма. Реальная empirical validation требует отдельного actual source; adapter/data join/consumer не подменяются вручную построенным graph.

### TEST-GRF-03-07 · temporal boundary/data-negative matrix
**NOT_RUN. REQ:** REQ-GRF-03-04.
**Setup:** Missing initial values, lag-unit mismatch, duplicate/shifted timestamps, insufficient historical window, foreign selected dataset, horizon outside declared support.
**Действие:** Same adapter/consumer before expensive numerical run.
**Oracle:** Точные unsupported/missing-source conditions, no zero-fill/future leakage/drop-lag. Допустимый subhorizon или descriptive source сохраняется только с явным scope; denied full horizon не становится complete result.
**Место:** `Selected temporal owner из DEC-TEMPORAL`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-GRF-03-08 · partial-family conditional useful result
**NOT_RUN. REQ:** REQ-GRF-03-05, REQ-GRF-03-06.
**Setup:** One supported known-direction graph; unresolved graph с двумя явно различными допустимыми hypotheses/completions для selected query; actual qualified family owner если найден.
**Действие:** Compare claimed invariant/family result либо conditional per-hypothesis output и fresh source binding.
**Oracle:** Если hypotheses дают разные эффекты/identification, single representative не выдаётся за invariant. Qualified owner сохраняет method/family assumptions; без owner unresolved source+reason и useful conditional hypothesis доступны. Synthetic topology не становится empirical world-model authority.
**Место:** `Canonical source/projection и selected partial-family owner из DEC-PARTIAL`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### Запуск: адаптируемый шаблон, не выполненная команда

Из `policy-engine/` в поддержанной Python3.14 среде с закреплёнными зависимостями. Этот документ не разрешает автоматические installs; отсутствующая dependency означает BLOCKED конкретной проверки.

```bash
python -V
python -m pytest -q tests/unit/remediation/test_grf_03.py tests/unit/foundry/methods/catalog/causal/test_gcm_fit.py tests/unit/foundry/methods/catalog/causal/test_gcm_query.py
# Selected DoWhy worker acceptance координируется с SCM-01; native_hybrid не заменяет его.
# Temporal/partial adapter tests добавляются только по конечным DEC и actual owner; все команды здесь NOT_RUN.
```

Фиксировать профиль/backend, inputs/seed/hash, deciding output и exit. Ruff и затронутые architecture/import checks выбирать по фактическому patch; native slot согласовать, полный suite на каждый пакет не копировать.

## 7. Общая интеграция и ownership

Переиспользовать **E02-I05-A, E02-I05-C**: [канонический контракт LANE-05](../03_Интеграция/LANE-05.md). Одно свидетельство связывается с конкретными вариантами и REQ; не считается многими независимыми подтверждениями.

GRF-03 координирует canonical projection/temporal boundary. SCM owners владеют fit/query/worker; любые shared-file changes интегрировать последовательно. Temporal/partial DEC конечны: named consumer, profile, positive/negative result либо конкретный unsupported claim. Native static repairs допускаются к приёмке отдельно от незавершённой общей capability.

- **GRF-02:** Lossless graph content/selected profiles и immutable preparation.
- **SCM-01 / SCM-02 / SCM-03:** Общие gcm_fit/query/source DTO; selected worker/twin semantics owners separate, один writer.
- **BKT-01:** Temporal adapter не заменяет feature availability/as-of validation реальных данных.

## 8. Совместимость, миграция и возврат

Сохранить compact lagged input bytes и source graph, не переписывать как static DAG. Новая finite expansion имеет explicit profile/version/mapping; old artifacts остаются историческими. Не менять default fit backend на hybrid ради прохождения тестов. Rollback temporal adapter возвращает named unsupported route с source/partial result, не игнорирует lag. Historical source dispositions не переаттестовываются автоматически.

## 9. Free-grow и обоснованные границы

- [universal-policy-design-target-architecture-and-gap.md — D0: hypothesis/model/typed capability](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): LLM предлагает структуру; reusable projection/time adapter проверяет выбранный смысл. Новый совместимый temporal case подключается через contract, не отдельный hardcoded model.
- [wave5-evidence-substitution-ratification.md — K01, K07–K08](../05_Основания/Архитектура/wave5-evidence-substitution-ratification.md): Source-preserving mathematical transformation не доказывает causal world model. Conditional useful result допустим без invented authority.

## 10. Конечные решения и сдача

### DEC-GRF-03-TEMPORAL
**Вопрос:** Какой actual temporal consumer нужен для одного полезного запроса?
**Кто решает:** Graph/model и selected temporal method owner.
**Конечное действие/выход:** Finite census текущих temporal methods/data contracts; выбрать existing consumer либо минимальную finite expansion у existing owner. Сдать profile/lag/time/initial mapping и TEST06–07; если empirical source недоступен, mechanism acceptance и practical limitation отдельно.
**До решения:** Static refusal сохраняется; ручной8-node graph не считается готовым adapter.

### DEC-GRF-03-PARTIAL
**Вопрос:** Требуется ли family-level inference или достаточно явной conditional hypothesis?
**Кто решает:** Causal identification/study owner.
**Конечное действие/выход:** Назвать intended query/family и available algorithm, проверить coverage supported profile; выбрать qualified family output либо per-hypothesis limited result с source binding. Сдать TEST08 и exact unsupported scope, не обещать общую PAG completeness.
**До решения:** Unknown marks не превращаются в arbitrary DAG; source и useful conditional research output сохраняются.

Сдать base/head и patch, exact REQ→TEST→shared variant, исходные входы и их идентичности, actual команды/exit/log, независимые численные/семантические oracles, positive/negative/removal controls, сохранённые инварианты и открытые решения. Source-only, fixture, native и scientific qualification отражать отдельно. Не повышать partial/NOT_RUN до PASS; квалифицированный локальный механизм не является автоматической готовностью всей политики.
