# CAU-04 — DoWhy: квалификация ограниченного backend без выдуманной неопределённости

**Исполнительская спецификация; финальная QA комплекта ещё ожидается.**
**LANE-05 · CP5 · B212, B213.** Основание `20d9009be21097bfbdc38a546a15cc60213b8ace`. Реализация документом не выполнена; все будущие проверки **NOT_RUN**. Именных исполнителя/reviewer назначает проект.

## 1. Практическая цель и область

Доказать реальное выполнение уже связанного linear ATE и доставку полезного partial результата. Не заказывать повторно исправленный epsilon-CI и не обещать NIE по recorder labels.

**Тип работы:** Preserve/qualify-only для выбранного профиля; отдельное ограниченное решение о legacy compatibility. Product change только при воспроизведённом несоответствии либо явно выбранном расширении.

[Аудит](../05_Основания/Аудит/02_Пакеты/CAU-04.md) · [остатки](../05_Основания/Аудит/01_Реестры/C55_остатки.json) · [исходная карточка](../05_Основания/Аудит/05_Источники/CAU-04_исходные_строки.txt) · [источники](../05_Основания/Аудит/05_Источники/C55_источники.json) · [трассировка](../04_Трассировка/CAU-04.json). Полные диагностические scripts/logs остаются в отдельно доставленном ZIP фазы 1. Действуют [общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## 2. Исходные обязанности и сохранение

B212: point-only уже сохраняется в NUMERICAL_FAILURE с CI/level=None, общий SUCCESS guard сохранён. B213: selected DoWhy 0.14 имеет точный estimand/contrast/target/level binding; broad legacy не квалифицирован. A10 оставляет numerical inference/scientific applicability отдельной работой. Нет нового R в C55.

- `preserve:0538`: Point без fabricated uncertainty → REQ-CAU-04-01; TEST-CAU-04-01, TEST-CAU-04-05.
- `preserve:0539`: Общий SUCCESS guard → REQ-CAU-04-01; TEST-CAU-04-01.
- `preserve:0540`: Selected exact ATE/linear/contrast/target/level profile → REQ-CAU-04-02; TEST-CAU-04-02, TEST-CAU-04-03.
- `preserve:0541`: Source/request/reply binding и full-report canonical projection → REQ-CAU-04-03, REQ-CAU-04-04; TEST-CAU-04-04, TEST-CAU-04-05.
- `preserve:0542`: Explicit legacy boundary и non-gating causal candidate → REQ-CAU-04-05, REQ-CAU-04-06; TEST-CAU-04-03, TEST-CAU-04-06, TEST-CAU-04-07.

## 3. Disposition полного остатка

| ID | Действие / причина | REQ / общий владелец |
|---|---|---|
| `C55-G01` | qualify: Actual backend, parent DTO/CAS и fresh consumer проверяются раздельно и совместно. | REQ-CAU-04-01, REQ-CAU-04-02, REQ-CAU-04-03, REQ-CAU-04-04 |
| `C55-G02` | lifecycle: Legacy API не равен selected profile; квалифицировать только заявленный finite scope. | REQ-CAU-04-02, REQ-CAU-04-06; CAU-05 |
| `C55-G03` | qualify: Отдельный numerical/DGP oracle и actual scientific assumptions, без promotion от content binding. | REQ-CAU-04-05 |

Все source-registry remaining также связаны: `remaining:0334`, `remaining:0335`, `remaining:0336`. Подробная причина и REQ для каждой строки — в companion JSON; повторная запись не считается новым независимым дефектом.

## 4. Нормативный контракт

### REQ-CAU-04-01
Finite point без доступного CI сохраняется в typed report как полезный partial result, без epsilon-CI, нулевого SE или confidence level. Настоящий CI сохраняет endpoints. SUCCESS требует действительной interval части; широкий heuristic failure envelope никогда не маркируется CI или gate-eligible.
Источник: B212; C55-G01. Проверки: TEST-CAU-04-01, TEST-CAU-04-05.

### REQ-CAU-04-02
Selected worker поддерживает ровно nonparametric-ate/backdoor.linear_regression/contrast 0→1/target ate/95%, binary treatment и full-rank design. Actual identify получает estimand и proceed_when_unidentifiable=False; identified adjustment set и effective estimator class/level совпадают с запросом. Unsupported request получает capability-result до numerical execution, не relabeled default.
Источник: B213; C55-G01, C55-G02. Проверки: TEST-CAU-04-02, TEST-CAU-04-03.

### REQ-CAU-04-03
Source-bound request сохраняет согласованные columns/rows/common row IDs, graph, parameters, seed и actual CAS source identity. Reply проверяет эти bindings и наблюдённый полный installed distribution inventory выбранного worker. Rehash изменённого outcome/graph/target не позволяет подменить admitted input.
Источник: B213; C55-G01. Проверки: TEST-CAU-04-04, TEST-CAU-04-05.

### REQ-CAU-04-04
Primary job и fresh consumer проверяют persisted/offered whole report и derived envelope, затем actual source/reply binding и canonical report_from_worker_result. Point/CI equality недостаточна: metadata, diagnostics, method_params, identified estimand и non-gating role также должны совпадать.
Источник: B212, B213; C55-G01. Проверки: TEST-CAU-04-05.

### REQ-CAU-04-05
В реальном locked DoWhy worker numerical point/SE/CI сравниваются с независимым Statsmodels OLS; фиксированный IID homoscedastic Gaussian DGP проверяется отдельно. Graph correctness, positivity и applicability к реальным данным не выводятся из hash/успеха backend/coverage синтетики; candidate остаётся полезным без authority promotion.
Источник: B212, B213; C55-G03. Проверки: TEST-CAU-04-02, TEST-CAU-04-06.

### REQ-CAU-04-06
Legacy-inprocess и GraphCausalDataV1 имеют явный ограниченный lifecycle: выполнить конечный caller/artifact census совместно с CAU-05. Не предлагать NIE/иные contrast как поддержанный production profile без actual version-specific API binding и numerical oracle. Отсутствие такого спроса допускает сохранение legacy с truthful unsupported/qualification boundary, не требует нового estimator.
Источник: B213; C55-G02. Проверки: TEST-CAU-04-03, TEST-CAU-04-07.

## 5. Конкретное техническое решение

Сначала запускать существующую реализацию, не переписывать partial contract. `_run_dowhy` ограничивает профиль, `worker.linear_ate` делает actual identify/estimate, `_validate_reply_fields` проверяет bindings, `report_from_worker_result` — единственный canonical producer полного отчёта. При новом несовпадении ремонтировать соответствующий owner, не добавлять второй способ вычисления report в Scientist.

Профили среды разделены: parent Python3.14 с настоящим registry/CAS и worker Python3.12/DoWhy0.14 по существующему lock. Зафиксировать interpreter, observed installed inventory, request/response digest и actual estimator class. Подготовка среды через общий разрешённый I1 процесс, не self-install каждого пакета. Point-only seam тест допустим для контрактного refusal, но численное свидетельство — только actual worker+independent OLS.

Для нового estimand сначала требуется существующее version-specific backend capability и handoff всех решающих parameters; новый label в report недостаточен. Если такого запроса нет, сохранить ограниченный рабочий ATE и явный unsupported результат. Это практический free-grow: общий registry/worker protocol расширяем, но не обязуемся изобрести универсальный causal estimator.

### Текущие owners и источники

- [policy-engine/src/polisyos/foundry/methods/catalog/causal/dowhy_identify_estimate.py:350–630](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/dowhy_identify_estimate.py#L350-L630)
- [policy-engine/workers/dowhy-014/worker.py:69–151](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/workers/dowhy-014/worker.py#L69-L151)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/_dowhy_worker.py:146–299](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/_dowhy_worker.py#L146-L299)
- [policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py:462–536](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py#L462-L536)
- [policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py:582–615](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py#L582-L615)
- [policy-engine/workers/dowhy-014/tests/test_worker.py:72–122](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/workers/dowhy-014/tests/test_worker.py#L72-L122)

## 6. Проверки: setup → действие → oracle

TEST-ID обозначает требуемую проверку, не существующий одноимённый pytest test. Расширять указанные действительные места, не дублировать suites.

### TEST-CAU-04-01 · native DTO/projection boundary
**NOT_RUN. REQ:** REQ-CAU-04-01.
**Setup:** Point7 без CI/SE, реальный interval[5,9], отдельно point+known SE без CI и unavailable backend.
**Действие:** Вызвать actual adapter/projection, JSON roundtrip и to_uncertainty_envelope.
**Oracle:** Partial point7 сохраняется; CI и level отсутствуют; реальный SE не затирается и не превращается автоматически в CI. Interval[5,9] не сужен. Failure envelope heuristic/non-gating, SUCCESS без CI отвергнут.
**Место:** `tests/unit/remediation/test_cau_04.py; ir/analytics/causal.py`.
**Doubles:** Recorder допустим только для отсутствия inference; не считается DoWhy numerical witness. DTO/projection реальные.

### TEST-CAU-04-02 · real worker numerical oracle
**NOT_RUN. REQ:** REQ-CAU-04-02, REQ-CAU-04-05.
**Setup:** workers/dowhy-014/tests/test_worker.py::request(seed=19,n=500), X→A,X→Y,A→Y, actual locked Python3.12/DoWhy0.14.
**Действие:** Через execute/linear_ate получить actual backend report; независимо fit Statsmodels OLS [1,A,X]; наблюдать actual arguments без подмены backend.
**Oracle:** Point/SE/95% CI совпадают с independent OLS abs1e-12; estimator class LinearRegressionEstimator, adjustment[X], level.95; inventory получен из runtime, не из fixture. Test не skip при отсутствующем backend: qualification BLOCKED, не PASS.
**Место:** `workers/dowhy-014/tests/test_worker.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-04-03 · native capability/negative
**NOT_RUN. REQ:** REQ-CAU-04-02, REQ-CAU-04-06.
**Setup:** NIE, ATT target, contrast1→2, level.8, unknown method/profile; positive default ATE.
**Действие:** Подать через ordinary registered route; подтвердить отсутствие worker dispatch для unsupported profile.
**Oracle:** Каждый unsupported получает INPUT_INVALID/unsupported_worker_profile без mislabeled point; default реально работает. Legacy NIE recorder отдельно доказывает только forwarding, не mathematical NIE.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py; test_dowhy_identify_estimate.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-04-04 · native source/protocol boundary
**NOT_RUN. REQ:** REQ-CAU-04-03.
**Setup:** Actual GraphCausalData CAS source; переставить только outcome values при тех же row IDs, изменить graph/seed/target; malformed reply primitives bool/string/nonfinite и неполный inventory.
**Действие:** Использовать actual _bound_request и reply validator; сохранить original valid request/reply control.
**Oracle:** Aligned original проходит; каждое mismatched content/source/request/effective-field отклонено до consumption. Coercion bool/string и invented inventory не проходят. Synthetic reply допустим для validator negatives, но отдельно labelled.
**Место:** `foundry/methods/catalog/causal/_dowhy_worker.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-04-05 · native two-environment E02-I05-B
**NOT_RUN. REQ:** REQ-CAU-04-01, REQ-CAU-04-03, REQ-CAU-04-04.
**Setup:** Primary causal job с actual CAS source и real selected worker; второй point-only controlled case на protocol seam; fresh store/reader.
**Действие:** Запустить _run_primary_causal_job, сохранить result, перечитать из CAS, выполнить full projection; затем изменить point, SE, CI, p-value, method_params, authority, diagnostic, identified estimand и корректно пересериализовать.
**Oracle:** Real interval reaches consumer. Point-only control remains useful without CI. Все восемь semantic mutations отказаны даже при согласованном hash нового payload; удалённый source также refused. Подмена только peer report/envelope не считается native custody.
**Место:** `scientist/nodes/builtins/simulate/run_causal_evaluation.py; existing selected-worker parent tests`.
**Doubles:** Synthetic panel допустим. Real numerical job не заменять recorder; point-only seam control помечать отдельно, не утверждать что реальный backend обязательно возвращает None.

### TEST-CAU-04-06 · bounded scientific qualification
**NOT_RUN. REQ:** REQ-CAU-04-05.
**Setup:** 200 независимых seeds1000..1199,n180, truth2, existing correctly specified IID Gaussian DGP.
**Действие:** Выполнить existing non-skipping coverage test; на каждом replicate сравнить actual CI с OLS abs1e-11, сохранить все исходы.
**Oracle:** 180≤covered≤199 из200 по заранее заданному band; не пересевать после результата. Это только указанный DGP/профиль, не real-data identification/NIE proof.
**Место:** `workers/dowhy-014/tests/test_worker.py::test_known_gaussian_dgp_nominal_95_coverage_over_independent_replicates`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-CAU-04-07 · finite lifecycle qualification
**NOT_RUN. REQ:** REQ-CAU-04-06.
**Setup:** Census фактических legacy execution_profile, V1 graph_gml и persisted FQN consumers с CAU-05.
**Действие:** Для каждого реально retained profile replay genuine supported fixture на actual installed version или зафиксировать точный отказ/миграцию.
**Oracle:** Таблица supported/replayable/unsupported с источником и сроком поддержки; неизвестная внешняя история не названа отсутствующей. Unsupported NIE не закрыт recorder test.
**Место:** `CAU-05 lifecycle owner; dowhy_identify_estimate.py::_run_legacy_dowhy`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### Запуск: адаптируемый шаблон, не выполненная команда

Из `policy-engine/` в поддержанной Python3.14 среде с закреплёнными зависимостями. Этот документ не разрешает автоматические installs; отсутствующая dependency означает BLOCKED конкретной проверки.

```bash
python -V
python -m pytest -q tests/unit/remediation/test_cau_04.py tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py tests/unit/foundry/methods/catalog/causal/test_dowhy_identify_estimate.py
# Из workers/dowhy-014 в подготовленной locked среде: python -m pytest -q tests/test_worker.py; отдельно parent native job suite.
```

Фиксировать профиль/backend, inputs/seed/hash, deciding output и exit. Ruff и затронутые architecture/import checks выбирать по фактическому patch; native slot согласовать, полный suite на каждый пакет не копировать.

## 7. Общая интеграция и ownership

Переиспользовать **E02-I05-B**: [канонический контракт LANE-05](../03_Интеграция/LANE-05.md). Одно свидетельство связывается с конкретными вариантами и REQ; не считается многими независимыми подтверждениями.

CAU-04 — estimator adapter/worker linear_ate и его focused tests. CAU-05 — lifecycle и shared whole-report acceptance. Worker protocol общий с SCM, changes сериализовать одним writer. Общий E02-I05-B запускается один раз для согласованного среза.

- **CAU-05:** Единый owner metadata/FQN lifecycle и общей report custody; CAU-04 отвечает за selected DoWhy semantics.
- **SCM-01/SCM-02:** Общий worker distribution/protocol owner, но gcm_fit/query не считается квалифицированным тестом linear_ate.

## 8. Совместимость, миграция и возврат

Текущие partial/interval и selected allowlist сохраняются. No mandatory schema change. Если меняется поддержанный inference profile, version и historical reader должны явно различать meaning; старые artifacts не переименовывать в новые authoritative results. Rollback ограничивает новый profile, не возвращает epsilon-CI.

## 9. Free-grow и обоснованные границы

- [policy-design-execution-topology.md — Applicability versus semantic judgment](../05_Основания/Архитектура/policy-design-execution-topology.md): LLM может предложить graph/estimand, но actual backend capability и causal assumptions не возникают из подписи.
- [universal-policy-design-target-architecture-and-gap.md — D0](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): Сохранять полезный partial candidate и расширяемый общий protocol, не специальный обход для каждого неподдержанного запроса.

## 10. Конечные решения и сдача

### DEC-CAU-04-LEGACY
**Вопрос:** Есть ли фактический потребитель broad legacy вне selected ATE?
**Кто решает:** CAU-04 с CAU-05 lifecycle reviewer.
**Конечное действие/выход:** Проверить tracked callers, declared support и доступные genuine artifacts. Для найденного профиля выбрать actual API qualification либо explicit migration/refusal; предъявить конкретные cases и boundaries.
**До решения:** Selected ATE остаётся supported; legacy NIE не получает production claim без numerical witness.

Сдать base/head и patch, exact REQ→TEST→shared variant, исходные входы и их идентичности, actual команды/exit/log, независимые численные/семантические oracles, positive/negative/removal controls, сохранённые инварианты и открытые решения. Source-only, fixture, native и scientific qualification отражать отдельно. Не повышать partial/NOT_RUN до PASS; квалифицированный локальный механизм не является автоматической готовностью всей политики.
