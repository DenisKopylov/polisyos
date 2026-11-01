# LANE-05 — Графы, причинные методы, SCM и повторное использование fit

**13 исполнительских пакетов подготовлены. Реализация и будущие проверки — NOT_RUN.** Базовый commit: `20d9009be21097bfbdc38a546a15cc60213b8ace`. Фаза 1 неизменна; полнота аудита не означает выполненного ремонта. [Общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## Цель и состав

Получить правильный условный расчёт на заявленных графе, данных, estimand и numerical profile, доставленный свежему потребителю без потери смысла. Идентификация, statistical inference и право применения проверяются отдельно. Partial model, point-only report и simulation-only result остаются полезными; отсутствие универсального deterministic model inventor не является дефектом.

| Пакет | Исходные ID | Практическая работа |
|---|---|---|
| [GRF-01](../02_Пакеты/GRF-01.md) | B216, B217, LA-007, LA-019 | Сохранение endpoint-aware separation/do surgery, native proof consumer и ограниченное retirement пустых siblings. |
| [GRF-02](../02_Пакеты/GRF-02.md) | B219, B220 | Direct Kuzu prewrite boundary с полезным bulk export; одна canonical preparation внутри query при сохранении внешнего admission. |
| [GRF-03](../02_Пакеты/GRF-03.md) | B214, B218 | Canonical graph projection; реальный temporal/partial-profile handoff либо точная граница, не arbitrary DAG. |
| [API-01](../02_Пакеты/API-01.md) | LA-020 | Сохранение явной facade/monkeypatch совместимости; полный finite import/FQN census и supported lifecycle. |
| [CAU-01](../02_Пакеты/CAU-01.md) | B204–B206, LA-016 этап 1 | Unit-label partition, CR0/HC1 и diagnostic semantics; normal quantile обоих callers, включая extreme-level boundary. |
| [CAU-02](../02_Пакеты/CAU-02.md) | B207–B209 | Квалификация staggered target/share influence, anticipation и finite-B bootstrap по независимым oracles. |
| [CAU-03](../02_Пакеты/CAU-03.md) | B210, B211 | Dimensionless conventional RDD solve без rank mismatch; сохранение настоящей bounded RBC/variance. |
| [CAU-04](../02_Пакеты/CAU-04.md) | B212, B213 | Реальный locked DoWhy ATE и native custody; point-only без выдуманного CI, truthful unsupported profiles. |
| [CAU-05](../02_Пакеты/CAU-05.md) | LA-016 этап 2 | Accountable dedicated cutover/replay lifecycle; shared whole-report acceptance, не повторная реализация metadata. |
| [SCM-01](../02_Пакеты/SCM-01.md) | B221, B222 | Twin relevant scope без ненужного root отказа; observed/joint carriers и общий polynomial predictor. |
| [SCM-02](../02_Пакеты/SCM-02.md) | B215, B223 | Ненулевая posterior covariance при смене единиц; finite joint-root conditioning; contrast и отдельная actual refit qualification. |
| [SCM-03](../02_Пакеты/SCM-03.md) | B224, B225 | Manual graph admission, canonical joint posterior replicas, сохранённые active plan и stochastic law. |
| [FIT-01](../02_Пакеты/FIT-01.md) | B54, B56 | Preserve/qualify immutable TMLE fit core с текущим view и реальным ограничением вложенной параллельности. |

Companion JSON связывают **41 audit residual record, 41 remaining obligation и 69 preservation obligations с 88 REQ и 103 TEST**. Это полнота документа, не 103 выполненных тестов. LA-016 — один исходный ID с двумя фазами. FIT-01 исторически CP4, остальные пакеты CP5: не добавлять FIT как общий CP5 барьер без затронутого маршрута.

## Порядок и единственные ответственные owners

### Графы и facade

GRF-01 сохраняет semantic oracle separation/surgery; GRF-02 — transport/cache; GRF-03 — canonical projection и declared static/temporal boundary. API-01 не удаляет реальные packages ради исчезнувших siblings. Точные исходные predecessors: GRF-02←GRF-01, GRF-03←GRF-02; API-01 исходных predecessors не имеет, graph owners — только фактические read-contract impacts. Реальные source/caller impacts уточняются до lease, а не трактуются как требование повторного patch уже исправленного predecessor.

`causal_graph.py` и `admg_ops.py` имеют одного writer в согласованном окне. Direct Kuzu mixed export не получает один лишь новый отказ: supported mixed caller должен реально пройти существующий lossless bulk route. Не отключать outer revalidation ради быстродействия.

### Causal estimators

CAU-01/02 владеют numerical standard/staggered paths. **CAU-05 — единый владелец shared whole-report lifecycle сценария и LA-016 closure**, но numerical oracle каждого метода остаётся у соответствующего CAU-пакета. CAU-03 владеет RDD; CAU-04 — DoWhy adapter/linear ATE. Общие `did.py`, `_common.py`, IR report и Scientist consumer не редактируются конкурентно.

Сначала numerical corrections и positive controls, затем actual registered report/custody, затем historical scope decision. Dedicated registry retirement не отменяется глобальным old-FQN alias: genuine supported frozen plans обрабатывает установленный versioned reader. Если corpus/support неизвестен, это явная ограниченная disposition, не fake replay PASS.

### SCM: явное распределение, без тройного ownership

| Единственный owner | Область | Соседние потребители/review |
|---|---|---|
| **SCM-03** | Common closure/prepared-plan API, manual graph admission и canonical posterior stream coordinates | SCM-01 потребляет план в twin; SCM-02 проверяет evidence/joint-law dependencies. |
| **SCM-02** | Conditional empirical row selector и scale-aware PSD/posterior factor; actual source-bound refit qualification | SCM-01/twin и GCM пользуются одним law owner; SCM-03 согласует coordinate mapping. |
| **SCM-01** | Twin consumer/admission/traversal integration и native selected fit→CAS→fresh query acceptance | SCM-03 поставляет общий план, SCM-02 — law/conditioning; общий worker не подменяется native_hybrid. |

Один patch-writer на общий `gcm_query.py`/`twin_network_query.py` в каждый момент. Последовательность: договориться о маленьком prepared-plan/law interface; SCM-03 admission/coordinate preparation; SCM-02 conditional law/factor; SCM-01 twin integration; затем единая связанная приёмка. Это координация тесно связанных правок, не runtime registry и не запрет локальных unit tests до полного объединения.

Closure учитывает обе arms, factual ancestors и зависимости объявленного joint law. **Non-ancestor observed root не обязательно irrelevant:** он может информировать другой root через общий empirical row carrier. GCM attribution уже поддерживает natural/stochastic comparator; public TwinNetworkQueryData в текущем профиле имеет две float ATOMIC arms — ТЗ не расширяет его молча.

Refit bootstrap — явная квалификация **SCM-02**, а не обещание будущего SCM-03. Native selected fit owner SCM-01 и refit consumer SCM-02 раздельны; один успешный linear_ate worker test CAU-04 не доказывает gcm_fit/refit.

### FIT-01 отдельно

TMLE cache/diagnostic view и actual process-pool budget принимаются через существующий fit owner. Это не DoWhy SCM fit и не причина нового shared cache/framework. Conditional inner-parallel decision требуется только при реальной потребности; default serial inner folds сохраняется, полезный cached fit не запускается заново ради свежей metadata.

## Общая интеграция

Канонические сценарии: [03_Интеграция/LANE-05.md](../03_Интеграция/LANE-05.md). Не копировать тяжёлую инфраструктуру в 13 suites.

| Сценарий | Ответственный за семейство | Варианты, связанные с локальными TEST |
|---|---|---|
| **E02-I05-A** | GRF-01 semantic consumer, GRF-02 transport contributor | Finite latent-DAG oracle; endpoint/do distinction; multiset/selected profile/copy/cache; manual projection controls; actual facade/bootstrap. |
| **E02-I05-B** | **CAU-05** | Standard/staggered/RDD independent numerical oracles; point-only/real interval; actual registered jobs, whole report/envelope, fresh reader, coherent substitution refusal. CAU-04 actual DoWhy в своей locked среде. |
| **E02-I05-C** | **SCM-01** для SCM native chain | Observed/joint roots, polynomial/manual profile, scale-aware posterior, conditional rows, active/tail law, exact source/profile custody. **SCM-02** принимает отдельный real refit вариант. **FIT-01** принимает отдельный TMLE cache/pool вариант, не заменяющий SCM worker. |

Профили: **P-CORE** — поддержанный Python3.14; **P-ANALYTICS** — реальные выбранные numerical dependencies; **P-DOWHY** — parent3.14 и isolated worker3.12/DoWhy0.14 с действующим lock. Подготовка через общий разрешённый процесс, не самостоятельные installs каждого пакета. Отсутствие среды — BLOCKED соответствующей квалификации, не новый product defect и не PASS.

Synthetic graph/panel/SCM разрешены как known-law oracle. Source-bound worker, actual registry/dispatcher, numerical producer, canonical serialization/CAS и fresh consumer не подменяются там, где принимается их работа. Mock-job tests сохраняются как отдельный узкий слой; они не закрывают genuine native chain. Point-only controlled protocol seam — не свидетельство, что real backend возвращал None.

## Разные типы результата и совместимость

- Structural proof подтверждает вывод **при заданном графе**, не истинность графа в реальном мире.
- Outcome/ITE distribution фиксированной SCM не estimator CI. Refit interval требует actual resampling/refitting, declared sampling unit и source-bound validation; его synthetic check не даёт real-data coverage автоматически.
- Non-gating report, partial source и неподдержанная posterior profile сохраняют полезные числа/модель с точной limitation. Не возвращать fabricated CI, default Normal или hidden atomic fallback.
- Historical graph/report/plan bytes не переписываются. Numerical correction, canonical stream mapping и schema/profile evolution различаются от equivalent relocation; old corrected replay и exact old flawed execution — разные claims.
- Canonical graph closure и numerical scaling поддерживают новый совместимый случай без ветки по имени политики. Новая семантика может потребовать обоснованного общего кода; бесконечная универсальность не требуется.

Дизайн: [универсальная политика, D0](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), [execution topology — applicability и semantic judgment](../05_Основания/Архитектура/policy-design-execution-topology.md), [evidence substitution K01/K07–K08](../05_Основания/Архитектура/wave5-evidence-substitution-ratification.md). LLM остаётся semantic proposer; mechanical integrity не присваивает scientific authority. Документы — ориентир практического решения, не повод строить новый абстрактный реестр вместо узкого ремонта.

## Сдача и границы готовности

Предъявить base/head/patch, точные REQ→TEST→scenario variant, inputs/seed/profile, actual command/log/exit, независимые oracle и removal controls, positive consumer result и сохранённые инварианты. Отдельно показать source-only, fixture, native и scientific evidence. Подготовленные здесь документы не выполняют тесты.

Закрытие локального repair не требует выдумывать внешний historical corpus или empirical authority. Но неизвестность должна иметь owner, конкретное bounded decision и честный статус; её нельзя терять за общим PASS. Shared acceptance связывает evidence один раз и не считает его несколькими независимыми научными экспериментами.


## Proposed v2: scientific acceptance уточнения

CAU-03 сохраняет coordinate/rank repair и настоящий RBC, но вводит явно selected conventional kernel-HC0 covariance profile и отдельное legacy weighted-residual readback решение (CS-001; TEST-CAU-03-08). Нельзя принимать inverse-variance WLS covariance как generic kernel inference. CAU-04 existing Statsmodels comparison — underlying-backend adapter parity; TEST-CAU-04-08 добавляет independent 8-row point/SE/CI oracle, DGP coverage остаётся отдельной (CS-002). FIT-01 сохраняет immutable fit-core/current-view/serial-inner; TEST-FIT-01-10 требует fold-owned continuous target preprocessing без heldout-Y leakage (CS-003). SCM-02 сохраняет full-row actual refits и shrink diagnostic; TEST-SCM-02-10 независимо проверяет каждый replica target и percentile endpoints (CS-005). Все новые проверки NOT_RUN, изменение продукта этим документом не утверждается. Новых REQ нет; четыре дополнительных local TEST не заменяют existing local/shared evidence.

### Точный selected native profile (CS-006)

Parent — Python>=3.14,<3.15 и parent lock. Selected existing DoWhy worker — **Linux, Python>=3.12,<3.13, DoWhy==0.14**, отдельный workers/dowhy-014 lock; actual worker.py guard, не parent extra dowhy<.14 marker. Native_hybrid/manual polynomial profiles не являются worker0.14 support. Runtime evidence фиксирует OS/architecture/interpreter/lock/extras/observed installed inventory; no backend install/import alone PASS. NetworkX3.6.1 и optional Kuzu0.11.3 представлены в parent lock; rustworkx absent требует отдельного declared authorized profile, иначе NOT_QUALIFIED. Kuzu upstream archived: retain minimal preflight/lossless-bulk compatibility, no mandatory migration or occurrence-aware expansion без actual caller need. Missing native profile ограничивает только соответствующую qualification, не отменяет полезные независимые repairs.
