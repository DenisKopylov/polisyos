# SCM-01 — Query-specific twin relevance и сохранённый выполняемый закон SCM

**Исполнительская спецификация; финальная QA комплекта ещё ожидается.**
**LANE-05 · CP5 · B221, B222.** Основание `20d9009be21097bfbdc38a546a15cc60213b8ace`. Реализация документом не выполнена; все будущие проверки **NOT_RUN**. Именных исполнителя/reviewer назначает проект.

## 1. Практическая цель и область

Устранить отказ outcome-only twin из-за действительно несущественного корня, не потеряв factual/joint-law dependencies. Сохранить observed roots и polynomial evaluator от producer до свежего consumer.

**Тип работы:** Bounded availability repair C57-R01; native qualification/test maintenance; explicit family/abduction boundary, не универсальный nonlinear fitter.

[Аудит](../05_Основания/Аудит/02_Пакеты/SCM-01.md) · [остатки](../05_Основания/Аудит/01_Реестры/C57_остатки.json) · [исходная карточка](../05_Основания/Аудит/05_Источники/SCM-01_исходные_строки.txt) · [источники](../05_Основания/Аудит/05_Источники/C57_источники.json) · [трассировка](../04_Трассировка/SCM-01.json). Полные диагностические scripts/logs остаются в отдельно доставленном ZIP фазы 1. Действуют [общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## 2. Исходные обязанности и сохранение

B221 observed/joint root carriers уже сохраняются; остаток whole-graph twin admission. B222 declared no-cross-term polynomial уже исполняется общим predictor, вместо linear surrogate. Original GRF-02 predecessor и shared SCM owners сохраняются. Refit qualification C58-G02 назначается SCM-02, не автоматически SCM-03.

- `preserve:0563`: Observed roots and joint row alignment → REQ-SCM-01-02, REQ-SCM-01-03; TEST-SCM-01-02, TEST-SCM-01-04.
- `preserve:0564`: Partial SCM with required-root refusal/explicit limited hypothesis → REQ-SCM-01-01, REQ-SCM-01-03; TEST-SCM-01-01, TEST-SCM-01-05.
- `preserve:0565`: Shared declared polynomial predictor and strict malformed payload rejection → REQ-SCM-01-04; TEST-SCM-01-06.
- `preserve:0566`: LINEAR positive control and shared-U twin → REQ-SCM-01-02, REQ-SCM-01-04; TEST-SCM-01-03, TEST-SCM-01-06.
- `preserve:0567`: Conservative non-gating distribution result → REQ-SCM-01-06; TEST-SCM-01-08.

## 3. Disposition полного остатка

| ID | Действие / причина | REQ / общий владелец |
|---|---|---|
| `C57-G01` | qualify: Actual selected worker/manifest/CAS/Scientist плюс точечное согласование stale schema assertion. | REQ-SCM-01-03, REQ-SCM-01-05 |
| `C57-R01` | fix: Один existing query/abduction relevance plan для admission/traversal; учитывает joint law, не только DAG. | REQ-SCM-01-01, REQ-SCM-01-02 |
| `C57-G03` | qualify: Полезный поддержанный polynomial подтверждается отдельно от general nonlinear inference. | REQ-SCM-01-04, REQ-SCM-01-06 |

Все source-registry remaining также связаны: `remaining:0350`, `remaining:0351`, `remaining:0352`. Подробная причина и REQ для каждой строки — в companion JSON; повторная запись не считается новым независимым дефектом.

## 4. Нормативный контракт

### REQ-SCM-01-01
Twin admission и traversal используют один согласованный relevant plan для requested outcome, обеих interventions и factual evidence. План включает structural ancestors после соответствующей surgery и все зависимости объявленного joint root/noise law, нужные для conditioning. Truly irrelevant disconnected root не блокирует outcome-only result; отсутствие действительно нужного закона не маскируется выдуманной Normal.
Источник: B221; C57-R01. Проверки: TEST-SCM-01-01, TEST-SCM-01-02, TEST-SCM-01-03.

### REQ-SCM-01-02
Сужение twin world сохраняет shared-U между arms, factual abduction и declared joint empirical root sampling. Observed auxiliary root может менять posterior outcome через joint carrier даже без DAG edge и не удаляется как non-ancestor. Intervention и observation не взаимозаменяемы; SCM-02 conditional-row owner задаёт поддержанный finite conditioning.
Источник: B221; C57-R01. Проверки: TEST-SCM-01-02, TEST-SCM-01-03, TEST-SCM-01-04.

### REQ-SCM-01-03
Fit/DTO/persisted readback сохраняют observed root samples, единый row alignment/group/source и malformed-carrier refusal. Partial SCM разрешена; missing required root даёт адресный отказ либо явно выбранную ограниченную hypothesis с identity/limitation, а полностью заменённый atomic do корень не требует natural law.
Источник: B221; C57-G01. Проверки: TEST-SCM-01-04, TEST-SCM-01-05.

### REQ-SCM-01-04
Declared additive_noise_poly выполняется одним _mechanism_predict в query/twin/fully observed residual, сохраняя degree и per-parent powers без cross terms. Malformed declared payload не fallback-ится на linear с polynomial noise. LINEAR и historical undeclared fallback semantics сохраняются отдельно.
Источник: B222; C57-G03. Проверки: TEST-SCM-01-06.

### REQ-SCM-01-05
Selected source-bound DoWhy GCM fit и explicit native_hybrid/manual polynomial profiles остаются различимыми. Native chain использует actual registry, worker где выбран, CAS, manifest-selected fresh reader и Scientist whole-output/request reconciliation. Current SCM schema1.2 и TwinNetworkResult1.1 — разные контракты; stale SCM1.1 assertion исправляется после проверки reader, не blanket замены всех1.1.
Источник: B221, B222; C57-G01. Проверки: TEST-SCM-01-07, TEST-SCM-01-08.

### REQ-SCM-01-06
Fixed-SCM outcome/ITE distribution и его heuristic range не выдаются за estimator CI/эмпирическую authority. Поддержанный fully observed polynomial residual не означает arbitrary nonlinear posterior или автоматический family selection. Для неизвестного профиля полезный candidate сохраняет точную limitation, а supported simple polynomial остаётся рабочим.
Источник: B222; C57-G03. Проверки: TEST-SCM-01-06, TEST-SCM-01-08.

## 5. Конкретное техническое решение

Перенести twin с whole-graph guard к подготовленному плану существующего query/abduction owner. План должен содержать отдельно arm traversal closure и factual conditioning closure, плюс необходимые joint-carrier/noise dependencies. Его вычисляют один раз из declared SCM/request; admission и simulation потребляют тот же план. Простого вызова DAG ancestors недостаточно: наблюдённый Z может информировать W через общий empirical row carrier без Z→Y. При неизвестной зависимости сохраняется conservative scope/limitation, не придуманная independence.

Для empty factual case с disconnected Z closure исключает Z; оба atomic arms заменяют X. Для partial factual case сохраняются все наблюдения, влияющие на posterior, и соответствующие law carriers. SCM-02 реализует finite empirical conditional-row selection; twin не добавляет своё несовместимое правило pin-root. Shared noise draw выполняется для нужного объединения узлов и используется в обеих worlds. Времена выполнения исключаются из equivalence oracle; вероятностный закон и declared stream reproducibility проверяются отдельно.

Root carriers и polynomial evaluator уже работают: сохранить общую функцию `_mechanism_predict`, strict declared payload validation и current profile identities. Native qualification объединить в E02-I05-C, не запускать отдельную дорогостоящую среду на каждый SCM packet. Source schema1.2 disagreement исправлять как test-maintenance после real reader check, не возвращать старый writer ради assertion.

### Текущие owners и источники

- [policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py:172–258](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L172-L258)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py:1238–1327](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L1238-L1327)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/twin_network_query.py:198–318](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/twin_network_query.py#L198-L318)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/twin_network_query.py:450–490](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/twin_network_query.py#L450-L490)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py:665–716](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py#L665-L716)
- [policy-engine/src/polisyos/ir/analytics/structural_causal_model.py:202–302](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/structural_causal_model.py#L202-L302)
- [policy-engine/src/polisyos/scientist/nodes/builtins/causal/run_causal_queries.py:252–393](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/causal/run_causal_queries.py#L252-L393)

## 6. Проверки: setup → действие → oracle

TEST-ID обозначает требуемую проверку, не существующий одноимённый pytest test. Расширять указанные действительные места, не дублировать suites.

### TEST-SCM-01-01 · native distinguishing relevance regression
**NOT_RUN. REQ:** REQ-SCM-01-01.
**Setup:** X→Y плюс disconnected Z, Y=X²; no X/Z mechanism; twin atomic armsX1/X2, empty factual condition. Controls Z≡0 и Z≡1e9.
**Действие:** Actual TwinNetworkQuery.pure_step и registered route; сравнить requested outputs без wall time с контролями, также GCM doX2.
**Oracle:** Без Z twin достигает consumer и ITE≈3; GCM outcome≈4. Добавление несовместимых irrelevant Z laws не меняет requested distributions/semantics. Old whole-graph guard должен провалить основной случай.
**Место:** `tests/unit/remediation/test_scm_01.py; twin_network_query.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-SCM-01-02 · native relevance negative/conditioning
**NOT_RUN. REQ:** REQ-SCM-01-01, REQ-SCM-01-02.
**Setup:** Z→Y с отсутствующим Z law; отдельно factual observation Z с зависимым joint root carrier (W,Z)=(0,0),(10,1),Y=T+W, conditionZ1.
**Действие:** Построить план для обеих arms и factual evidence; выполнить conditional query/twin только если выбранный profile поддерживает закон.
**Oracle:** Необходимый missing Z отказывает без opt-in; observed auxiliary Z не исключён лишь потому, что не ancestorY. Поддержанный finite joint conditional law даёт W10; до реализации этого профиля exact claim запрещён и limitation/refusal адресная. Согласовать положительный finite case SCM-02 TEST-04.
**Место:** `Existing active query/abduction owners и SCM-02 joint-row conditioning`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-SCM-01-03 · native surgery/shared-noise control
**NOT_RUN. REQ:** REQ-SCM-01-01, REQ-SCM-01-02.
**Setup:** На существующем GCM attribution/shared-plan route один ancestor нужен только natural comparator arm; другой влияет на factual evidence. Отдельный public TwinNetworkQueryData control использует две поддержанные float ATOMIC arms и shared Gaussian U с ненулевой marginal variance.
**Действие:** Планировать union двух arm scopes и abduction scope; получить обе world arrays на same sampled U.
**Oracle:** Нет потери нужного ancestor/наблюдения; natural comparator не становится do0. Marginal law сохраняется, ITE использует общий U, а не независимые worlds. Structural-only slicing намеренно должен провалить joint-law negative.
**Место:** `twin_network_query.py::_twin_simulate_samples; gcm_query.py::_active_query_nodes`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-SCM-01-04 · native observed carrier roundtrip
**NOT_RUN. REQ:** REQ-SCM-01-02, REQ-SCM-01-03.
**Setup:** T=[0,0,1,1,2,2],Z=[99,101,99,102,99,100],Y=3T+2Z; native_hybrid fitted SCM.
**Действие:** Fit→actual DTO→JSON→query; natural joint samples и doT1 n1024 seed7; malformed lengths/source/group/family negatives.
**Oracle:** Natural pairs только исходные aligned rows. doT1 support{201,203,205,207}, mean соответствует finite empirical mean203 в предзаданном Monte Carlo bound, не3. Неправильные carriers отказаны, независимость из отдельных arrays не выдумана.
**Место:** `tests/unit/remediation/test_scm_01.py; structural_causal_model.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-SCM-01-05 · native partial-model boundary
**NOT_RUN. REQ:** REQ-SCM-01-03.
**Setup:** Missing root feeding outcome, irrelevant missing root и root полностью заменённый atomic do; explicit hypothesis opt-in отдельный case.
**Действие:** Вызвать query/twin с default и opt-in.
**Oracle:** Default отказывает только при необходимом отсутствии; valid partial case проходит. Opt-in result сохраняет declared hypothesis identity и non-gating limitation, не называется fitted law.
**Место:** `gcm_query.py::_required_missing_root_nodes; twin admission owner`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-SCM-01-06 · native declared family oracle
**NOT_RUN. REQ:** REQ-SCM-01-04, REQ-SCM-01-06.
**Setup:** 101x∈[-2,2],y=x² actual fitter payload; LINEAR y=1+3x; factualX1,Y1.25; incomplete coefficients и degree2.5.
**Действие:** Stored payload roundtrip→query doX2; shared predictor residual и twin arms1/2.
**Oracle:** Polynomial≈4, не1.36; LINEAR7; residual≈.25 и counterworld≈4.25; malformed declared payload отказан, no silent linear downgrade. Это manual/retained helper profile, не automatic selected nonlinear fitting.
**Место:** `tests/unit/remediation/test_scm_01.py; _fit_additive_noise_poly/_mechanism_predict`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-SCM-01-07 · native selected fit→CAS→fresh reader E02-I05-C
**NOT_RUN. REQ:** REQ-SCM-01-05.
**Setup:** Actual source-bound static observed DAG и declared mechanisms; real selected DoWhy worker в согласованной среде.
**Действие:** Выполнить fit, сохранить SCM, открыть свежим profile-selected reader, запустить query через Scientist; compare full mechanism/root/training/provenance content.
**Oracle:** Actual fitted law доходит до query; removed/substituted source, profile или mechanism payload адресно refused. native_hybrid не объявляется DoWhy; mock worker не засчитывается numerical fit witness.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_gcm_backend_contract.py; test_gcm_query.py; scientist/nodes/builtins/causal/run_causal_queries.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-SCM-01-08 · native schema/test maintenance + distribution semantics
**NOT_RUN. REQ:** REQ-SCM-01-05, REQ-SCM-01-06.
**Setup:** Current SCM1.2 и genuine legacy fixtures по поддержанному reader; independent TwinNetworkResult1.1; persisted query request/results.
**Действие:** Сверить stale test_gcm_backend_contract expectation, заменить только неверный SCM expectation с characterization; actual report→envelope fresh path.
**Oracle:** Current SCM accepted как1.2, Twin schema не меняется автоматически. Historical read только по своему versioned contract. Outcome/ITE range не CI, estimator_interval отсутствует без refit evidence, gate_eligible=False.
**Место:** `test_gcm_backend_contract.py:195–205; ir/analytics/twin_network.py::TwinNetworkResult`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### Запуск: адаптируемый шаблон, не выполненная команда

Из `policy-engine/` в поддержанной Python3.14 среде с закреплёнными зависимостями. Этот документ не разрешает автоматические installs; отсутствующая dependency означает BLOCKED конкретной проверки.

```bash
python -V
python -m pytest -q tests/unit/remediation/test_scm_01.py tests/unit/foundry/methods/catalog/causal/test_gcm_backend_contract.py tests/unit/foundry/methods/catalog/causal/test_gcm_query.py
# Shared actual worker/source-bound scenario E02-I05-C, не mock run_job-only qualification.
```

Фиксировать профиль/backend, inputs/seed/hash, deciding output и exit. Ruff и затронутые architecture/import checks выбирать по фактическому patch; native slot согласовать, полный suite на каждый пакет не копировать.

## 7. Общая интеграция и ownership

Переиспользовать **E02-I05-C**: [канонический контракт LANE-05](../03_Интеграция/LANE-05.md). Одно свидетельство связывается с конкретными вариантами и REQ; не считается многими независимыми подтверждениями.

SCM-01 владеет twin consumer/relevance integration и native selected fit→query acceptance. SCM-03 — единственный writer common closure/prepared-plan API и canonical stream coordinates. SCM-02 — единственный writer conditional-row/PSD и владелец refit qualification. Один writer gcm_query.py/twin_network_query.py в связанной очереди; source/DTO changes review с GRF-03. Никакой отдельной simulation engine.

- **GRF-02:** Оригинальный predecessor: canonical graph identity/immutable adjacency.
- **SCM-02:** SCM-02 — единственный writer conditional-row/PSD и owner refit qualification; empirical root evidence требует joint conditioning, не removal non-ancestor.
- **SCM-03:** SCM-03 — единственный writer common closure/prepared-plan API и canonical stream coordinates; twin потребляет этот API, не копирует planner.
- **GRF-03:** Canonical static DAG/source disposition, temporal restriction не обходить.

## 8. Совместимость, миграция и возврат

Для truly irrelevant roots отказ заменяется useful result — intentional availability delta. Needed-root refusal и explicit hypothesis сохраняются. Current law/profile и persisted source identity не переписывать; full-world API, если существует, не сужать outcome-only правилом. Если распределение RNG stream меняется, объявить replay profile/version согласно SCM-03, не обещать старые draws без доказательства.

## 9. Free-grow и обоснованные границы

- [universal-policy-design-target-architecture-and-gap.md — D0](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): Общий query-specific plan поддерживает новые compatible graphs без hardcodedX/Y/Z; second joint-law case проверяет содержательность, не blanket guard.
- [policy-design-execution-topology.md — Applicability versus semantic judgment](../05_Основания/Архитектура/policy-design-execution-topology.md): LLM model proposal и вычислимый polynomial не равны empirical identification; limited useful model не запрещается глобально.

## 10. Конечные решения и сдача

### DEC-SCM-01-CLOSURE
**Вопрос:** Какие declared law dependencies должен включать current supported posterior scope?
**Кто решает:** SCM-03 — единственный writer common closure/prepared-plan API; SCM-02 reviewer conditional-law, SCM-01 twin consumer.
**Конечное действие/выход:** Сопоставить finite profiles independent Gaussian, aligned empirical roots и fully observed polynomial residual; задать один closure interface с двумя arm scopes и evidence dependencies. Проверить irrelevant removal, needed ancestor и auxiliary observed joint-root controls.
**До решения:** Не исключать зависимость только по отсутствию DAG edge; unsupported law остаётся conservative/limited, не exact.

Сдать base/head и patch, exact REQ→TEST→shared variant, исходные входы и их идентичности, actual команды/exit/log, независимые численные/семантические oracles, positive/negative/removal controls, сохранённые инварианты и открытые решения. Source-only, fixture, native и scientific qualification отражать отдельно. Не повышать partial/NOT_RUN до PASS; квалифицированный локальный механизм не является автоматической готовностью всей политики.
