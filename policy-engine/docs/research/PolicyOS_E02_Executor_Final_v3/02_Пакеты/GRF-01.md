# GRF-01 — Native квалификация static ADMG separator/perfect-do и сохранённых packages

**Исполнительская спецификация; финальная QA комплекта ещё ожидается.**
**LANE-05 · CP5 · B216, B217, LA-007, LA-019.** Основание `20d9009be21097bfbdc38a546a15cc60213b8ace`. Реализация документом не выполнена; все будущие проверки **NOT_RUN**. Именных исполнителя/reviewer назначает проект.

## 1. Практическая цель и область

Довести уже исправленные endpoint-aware separation и perfect intervention до настоящих rule/ID/IDC/artifact consumers. Подтвердить точечный retirement пустых siblings в installed distribution, не восстанавливая их и не удаляя реальные causal packages.

**Тип работы:** Preserve/qualify-only: новых подтверждённых R нет; product change только при новом воспроизведённом несоответствии или установленном integration gap.

[Аудит](../05_Основания/Аудит/02_Пакеты/GRF-01.md) · [остатки](../05_Основания/Аудит/01_Реестры/C48_остатки.json) · [исходная карточка](../05_Основания/Аудит/05_Источники/GRF-01_исходные_строки.txt) · [источники](../05_Основания/Аудит/05_Источники/C48_источники.json) · [трассировка](../04_Трассировка/GRF-01.json). Полные диагностические scripts/logs остаются в отдельно доставленном ZIP фазы 1. Действуют [общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## 2. Исходные обязанности и сохранение

B216: общий separator уже использует incoming/outgoing endpoint marks, collider и An(Z). B217: perfect-do удаляет incoming directed и incident bidirected, сохраняя outgoing. LA-007/LA-019: три точных пустых .py уже отсутствуют; id_engine/, causal_engine/, interference/ защищены. LK05/LK13 не позволяют превратить локальный cleanup в удаление ID/BERL семейства. A07 про factual ancestors/shared noise не означает квалифицированной counterfactual способности данного пакета.

- `preserve:0553`: Canonical static ADMG admission и endpoint marks → REQ-GRF-01-01; TEST-GRF-01-01, TEST-GRF-01-02.
- `preserve:0554`: Perfect-do cuts incoming/incident bidirected, сохраняет outgoing → REQ-GRF-01-02; TEST-GRF-01-01, TEST-GRF-01-03.
- `preserve:0555`: Immutable graph metadata и validated cache boundary → REQ-GRF-01-01, REQ-GRF-01-02; TEST-GRF-01-02, TEST-GRF-01-03.
- `preserve:0556`: Настоящие id_engine/causal_engine/interference packages → REQ-GRF-01-04; TEST-GRF-01-05, TEST-GRF-01-06.
- `preserve:0557`: Независимый finite latent-DAG oracle и typed proof consumers → REQ-GRF-01-03, REQ-GRF-01-06; TEST-GRF-01-01, TEST-GRF-01-03, TEST-GRF-01-04.

## 3. Disposition полного остатка

| ID | Действие / причина | REQ / общий владелец |
|---|---|---|
| `C48-G01` | qualify: Native supported imports/rules/ID/IDC/artifact lifecycle, no algorithm rewrite by default. | REQ-GRF-01-01, REQ-GRF-01-02, REQ-GRF-01-03, REQ-GRF-01-06 |
| `C48-G02` | qualify: Installed compatibility and finite filename-loader qualification; retirements already applied. | REQ-GRF-01-04 |
| `C48-G03` | qualify: Static profile/scientific graph basis boundaries and useful conditional consumer. | REQ-GRF-01-01, REQ-GRF-01-02, REQ-GRF-01-05 |

Все source-registry remaining также связаны: `remaining:0344`, `remaining:0345`, `remaining:0346`. Подробная причина и REQ для каждой строки — в companion JSON; повторная запись не считается новым независимым дефектом.

## 4. Нормативный контракт

### REQ-GRF-01-01
Сохранить общий canonical static ADMG admission и endpoint-aware m-separation: fork/chain открыты без conditioned middle, collider закрыт до conditioning collider/descendant; symmetric query и переименование узлов не меняют ответ. Warm cache не обходит повторную проверку raw graph content/profile. Partial/PAG/temporal профили не получают static success молча.
Источник: B216; C48-G01, C48-G03. Проверки: TEST-GRF-01-01, TEST-GRF-01-02.

### REQ-GRF-01-02
Perfect-do удаляет incoming directed edges и все incident bidirected у action nodes, не удаляя outgoing effects и latent influence на остальных узлах. Reverse-stored directed marks и multiple actions имеют ту же семантику. Graph input/metadata неизменны; conditioning/fixing/stochastic intervention не подменяются этой операцией.
Источник: B217; C48-G01, C48-G03. Проверки: TEST-GRF-01-01, TEST-GRF-01-03.

### REQ-GRF-01-03
Actual do/sigma rule consumers возвращают корректно изменённый DistributionRef и typed ProofStep, либо не применяют правило. Native ID/IDC и recursive rewrite выбранных маленьких positive/nonidentifiable запросов сохраняют graph/query/estimand/proof bindings при persistence/fresh read. Исправление separator не объявляется доказательством полноты всего ID/IDC.
Источник: B216, B217; C48-G01. Проверки: TEST-GRF-01-03, TEST-GRF-01-04.

### REQ-GRF-01-04
Точные retired id_engine.py/causal_engine.py/interference.py не возвращаются. Native find_spec/public imports и wheel/sdist разрешают реальные packages и нужные public objects. Проверяются finite repository filename-loader/package-data/generated inventories и declared external support window; неизвестные внешние динамические loaders не считаются доказанно отсутствующими.
Источник: LA-007, LA-019; C48-G02. Проверки: TEST-GRF-01-05, TEST-GRF-01-06.

### REQ-GRF-01-05
Пользовательский causal result связывает выбранное graph basis/revision, estimand/query, proof и доступные observations/assumptions с конкретным scope. Structural идентификация может быть полезным conditional результатом без empirical calibration; synthetic finite graph oracle не становится observed model validity или policy authority. LLM может предложить граф, но его гипотеза не превращается в установленную причинную структуру.
Источник: B216, B217; C48-G03. Проверки: TEST-GRF-01-04, TEST-GRF-01-07.

### REQ-GRF-01-06
Конечный independent differential corpus выполняется один раз в общем lane profile:200 трёхузловых ADMG,2400 separation queries,19200 surgery queries с explicit latent DAG/moralization oracle. Сохранить отдельные small regressions и actual package imports без namespace shells; bounded прежние PASS не заменяют поддержанный Python/dependency run.
Источник: B216, B217; C48-G01. Проверки: TEST-GRF-01-01, TEST-GRF-01-03, TEST-GRF-01-04.

## 5. Конкретное техническое решение

Изменение продукта по умолчанию **не требуется**: endpoint-state traversal и correct incoming/bidirected surgery уже присутствуют. First action — supported native exact owners и independent finite oracle, затем actual rule→ID/IDC→artifact route. Не добавлять ещё один separator, fallback flag или global AND. Если regression появляется в current native environment, исправление остаётся у `admg_ops`/actual consumer с минимальным distinguishing case, а не переписыванием ID-engine.

Кеш получает canonical validated graph, immutable adjacency и сохранённые metadata; repeat boundary validation обязательна даже при cache hit. Static partial/PAG/temporal profiles остаются явно separate: отсутствие поддержки не лечится удобной интерпретацией marks. Для пользовательской цепочки использовать существующие graph artifact/estimand/proof owners и exact refs; если discovered gap в transport, донести missing existing binding, не создавать второй evidence registry.

Три пустых sibling .py уже отсутствуют. LA acceptance теперь состоит в установленном distribution/public-loader evidence, а не повторном удалении. API-01 владеет substantive facade surface. Supported file-loader dependency, если найдена, мигрирует к реальному package API; внешнее неизвестное окно описать честно. LK05/LK13 исключают recursive cleanup реальных packages/BERL.

Structural graph correctness отвечает на вопрос при заданной гипотезе. Source/measurement/causal assumptions проверяются у actual domain owners и остаются visible; полезный conditional ID/estimand не требует invented authenticated issuer. Новая совместимая static graph topology должна работать через тот же contract, новая semantics — separate justified profile.

### Текущие owners и источники

- [policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py:184–307](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py#L184-L307)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py:485–584](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py#L485-L584)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py:699–801](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py#L699-L801)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/do_calculus.py:80–267](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/do_calculus.py#L80-L267)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/id_engine/core.py:1081–1253](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/id_engine/core.py#L1081-L1253)
- [policy-engine/tests/unit/foundry/methods/catalog/causal/test_admg_latent_oracle.py:1–164](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_admg_latent_oracle.py#L1-L164)

## 6. Проверки: setup → действие → oracle

TEST-ID обозначает требуемую проверку, не существующий одноимённый pytest test. Расширять указанные действительные места, не дублировать suites.

### TEST-GRF-01-01 · native independent finite graph oracle
**NOT_RUN. REQ:** REQ-GRF-01-01, REQ-GRF-01-02, REQ-GRF-01-06.
**Setup:** Existing test_admg_latent_oracle.py:25 directed DAGs×8 bidirected subsets; ordered pairs and conditioning sets;8action sets.
**Действие:** Native pytest настоящего module; reference latent common causes→ancestors/moralization/connectivity, runtime endpoint traversal.
**Oracle:** 0 mismatches для2400 separation и19200 surgery queries; denominator/counts/log сохранены. Oracle не копирует runtime algorithm. Это finite3node result, не proof всех n/PAG/temporal.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_admg_latent_oracle.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-GRF-01-02 · native profile/cache/renaming matrix
**NOT_RUN. REQ:** REQ-GRF-01-01.
**Setup:** Chain,fork,collider,bidirected collider,conditioned descendant; reverse storage, renamed/permuted nodes; warmed valid cache затем invalid marks/PAG/lag>0.
**Действие:** Actual m_separation/d_separation/public admission.
**Oracle:** Expected opening/closing, X/Y symmetry и rename invariance; invalid profile rejected до cached answer. DAG-only API не принимает bidirected. Никакой двусторонний AND не используется вместо правильного примитива.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_admg_profile_consumers.py; admg_ops.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-GRF-01-03 · native rules with proof oracle
**NOT_RUN. REQ:** REQ-GRF-01-02, REQ-GRF-01-03, REQ-GRF-01-06.
**Setup:** X↔Y; P→X→Y+X↔Z; reverse-stored equivalents; multiple action set. DistributionRef для Rule1/2/3 и sigma variants.
**Действие:** Actual surgery/rules и recursive do-calculus postpass; inspect AST leaves/ProofStep, original DTO dump.
**Oracle:** do(X) убирает confounding/incoming, оставляет X→Y; Rule3 pureconfounding removes do(X), fork Rule1 не удаляет зависимое conditioning, collider eligible does. Rule2 uses outgoing surgery separately. Original bytes-equivalent graph fields/metadata preserved; proof describes actually applied operation.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_do_calculus_postpass.py; test_sigma_calculus.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-GRF-01-04 · native ID/IDC→artifact→fresh consumer E02-I05-A
**NOT_RUN. REQ:** REQ-GRF-01-03, REQ-GRF-01-05, REQ-GRF-01-06.
**Setup:** Small supported DAG positive ID/IDC query, separate known nonidentifiable ADMG and invalid query/profile; real CausalEngine and selected graph artifact/CAS.
**Действие:** Actual identify/rewrite→persist result/proof→fresh CausalEngine consumer; IDC withZempty and conditional query.
**Oracle:** Positive estimand/proof/distributions match hand-established query, IDC preserves denominator positivity condition. Nonidentifiable preserves certificate/reason, not fabricated AST; invalid profile refused. Fresh output bound to same graph/query/revision, conditional assumptions visible. No claim all ID/IDC cases complete.
**Место:** `tests/unit/foundry/methods/test_causal_engine_integration.py; tests/unit/foundry/methods/catalog/causal/test_id_engine_extensions.py`.
**Doubles:** Synthetic graph/data permissible for structural mechanism. Actual graph model, admission, rules, ID/IDC, CAS and selected loader cannot be stubs.

### TEST-GRF-01-05 · native installed public surfaces
**NOT_RUN. REQ:** REQ-GRF-01-04.
**Setup:** Supported Python3.14 actual wheel/sdist built in coordinated packaging profile; clean environment outside checkout import shadowing.
**Действие:** find_spec/import id_engine,causal_engine,interference; exercise representative public function/class and inspect package origin/distribution inventory.
**Oracle:** Origins package __init__.py, real core/transport/counterfactual/api exports present; three retired sibling files absent. Actual selected inference callable works, not just import-name presence. API-01 surface evidence reused where exact profile matches.
**Место:** `causal/id_engine/__init__.py; causal/causal_engine/__init__.py; causal/interference/__init__.py; tests/unit/foundry/methods/catalog/causal/test_causal_engine_runtime_exports.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-GRF-01-06 · finite filename-loader lifecycle qualification
**NOT_RUN. REQ:** REQ-GRF-01-04.
**Setup:** Tracked src/tests/config/generated package-data/source inventory, supported filename-loader contracts and available external consumer evidence.
**Действие:** Classify exact retired-path hits as executable/declaredcompatibility/history; test identified supported loaders or migrate caller to package API.
**Oracle:** No supported loader silently depends on deleted empty file; historical text not treated executable. Unknown external paths explicitly bounded by declared support window. No blanket deletion by prefix, no empty shim resurrection to satisfy path count.
**Место:** `Repository packaging/public-surface inventory; shared LANE-12 packaging profile`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-GRF-01-07 · scoped graph-basis positive/negative
**NOT_RUN. REQ:** REQ-GRF-01-05.
**Setup:** LLM/test-proposed graph with explicit assumptions and one selected observed dataset; second materially different supported static graph/query through same contract; foreign graph ref and unestablished empirical basis.
**Действие:** Selected graph→estimand/proof→fresh result consumer; inspect scope/limitations.
**Oracle:** Both supported hypotheses produce useful structural conditional answer without case-name branch. Foreign graph/query binding rejected; unestablished empirical basis stays hypothesis/assumption, not authority. PAG/temporal request returns named unsupported profile rather than guessed completion.
**Место:** `CausalEngine selected graph/artifact route; E02-I05-A`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### Запуск: адаптируемый шаблон, не выполненная команда

Из `policy-engine/` в поддержанной Python3.14 среде с закреплёнными зависимостями. Этот документ не разрешает автоматические installs; отсутствующая dependency означает BLOCKED конкретной проверки.

```bash
python -V
python -m pytest -q tests/unit/foundry/methods/catalog/causal/test_admg_latent_oracle.py tests/unit/foundry/methods/catalog/causal/test_admg_profile_consumers.py
python -m pytest -q tests/unit/foundry/methods/catalog/causal/test_do_calculus_postpass.py tests/unit/foundry/methods/catalog/causal/test_sigma_calculus.py tests/unit/foundry/methods/catalog/causal/test_id_engine_extensions.py
python -m pytest -q tests/unit/foundry/methods/test_causal_engine_integration.py
# Wheel/sdist и installed imports объединить с actual LANE-12 packaging job; не запускать installs автоматически.
```

Фиксировать профиль/backend, inputs/seed/hash, deciding output и exit. Ruff и затронутые architecture/import checks выбирать по фактическому patch; native slot согласовать, полный suite на каждый пакет не копировать.

## 7. Общая интеграция и ownership

Переиспользовать **E02-I05-A**: [канонический контракт LANE-05](../03_Интеграция/LANE-05.md). Одно свидетельство связывается с конкретными вариантами и REQ; не считается многими независимыми подтверждениями.

GRF-01 координирует common separator/surgery и finite oracle; GRF-02 — adjacency performance/graph adapter; GRF-03 — DAG export; API-01 — facade. Shared E02-I05-A один. Installed packaging принимается вместе с LANE-12 CP6; локальная mathematical qualification может быть принята раньше с явно открытым packaging остатком.

- **GRF-02 / GRF-03:** Общий admg_ops admission/cache/topology owner; не снимать outer validation ради экономии.
- **API-01:** Public facade identity/installed evidence shared; не смешивать точечное sibling retirement с facade migration.
- **SCM-01 / SCM-02:** Perfect-do structural semantics не доказывает factual abduction/shared-noise query correctness; отдельный E02-I05-C.
- **LANE-12:** Одна coordinated wheel/sdist/public-surface qualification, не build на каждый пакет.

## 8. Совместимость, миграция и возврат

Сохранять exact graph/proof public types, package exports, reverse-storage semantics и input immutability. No planned product diff for passing repairs. Если native repair нужен, historical proof не переписывается; current recomputation привязывается к current algorithm/profile. Retirement не возвращается пустым shim ради unknown dynamic consumers. Unsupported graph family остаётся явной limitation, не silent static projection.

## 9. Free-grow и обоснованные границы

- [universal-policy-design-target-architecture-and-gap.md — D0 и reusable causal capabilities](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): Один endpoint-aware mechanism принимает новые совместимые static graphs, не меню разрешённых policy examples; semantic proposer может быть LLM.
- [wave5-evidence-substitution-ratification.md — K01/K07–K08](../05_Основания/Архитектура/wave5-evidence-substitution-ratification.md): Structural proof и canonical identity не заменяют empirical graph basis либо права применения политики.

## 10. Конечные решения и сдача

### DEC-GRF-01-PACKAGING
**Вопрос:** Есть ли поддержанный exact-filename consumer трёх retired siblings?
**Кто решает:** Causal public API/release owner.
**Конечное действие/выход:** TEST06 finite census + declared external support window; если есть supported caller, мигрировать его к package API и проверить installed distribution. Если нет — зафиксировать bounded scope, не обещать глобальное отсутствие динамических путей.
**До решения:** Сохраняются настоящие packages, пустые siblings не восстанавливаются.

### DEC-GRF-01-SCOPE
**Вопрос:** Какое основание causal graph необходимо для выбранного пользовательского claim?
**Кто решает:** Selected graph/study owner.
**Конечное действие/выход:** Для одного intended use назвать graph hypothesis/revision, observations/assumptions и estimand scope; показать conditional positive и foreign-binding negative в TEST07. Не требовать универсального causal model inventor.
**До решения:** Полезный structural conditional result с explicit empirical unknowns.

Сдать base/head и patch, exact REQ→TEST→shared variant, исходные входы и их идентичности, actual команды/exit/log, независимые численные/семантические oracles, positive/negative/removal controls, сохранённые инварианты и открытые решения. Source-only, fixture, native и scientific qualification отражать отдельно. Не повышать partial/NOT_RUN до PASS; квалифицированный локальный механизм не является автоматической готовностью всей политики.
