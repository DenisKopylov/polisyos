# CAU-04 — DoWhy: point-only без фиктивного CI, связанный ограниченный профиль
## C55 · 1 ноября 2026 года

**Порядок:** 55/127, LANE-05. **Исходные IDs:** B212, B213. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит. Свежая проверка после внешнего сохранения C54; утраченный прежний C55 не используется.

## Решение

Исходный epsilon-CI не воспроизведён: finite point=7 без inference сохраняется в actual typed `NUMERICAL_FAILURE` report, с CI/level/SE=None. Настоящий fixture interval [5,9] сохраняется. Общий SUCCESS guard не ослаблен. Выбранный default путь теперь ограничен **DoWhy0.14 / linear backdoor ATE / contrast0→1 / population ate /95%** и не выдаёт NIE или ATT под новым label.

**7 bounded MATCH, 13 unchanged test bodies /24 cases PASS изолированно. Нового R не подтверждено.** Actual adapter/DTO, bridge validators, standalone protocol/numeric helpers и whole-report consumer исполнены в ограниченном harness. **Настоящее численное выполнение DoWhy, supported native DTO/registry/CAS и coverage не выполнены:** это G, а не ложный backend PASS.

## 1. Матрица исходных ID

| ID | Исходная проблема | Подтверждено в текущем срезе | Остаток |
|---|---|---|---|
| B212 | Point-only превращался в point±epsilon и SUCCESS | Actual partial report сохраняет point отдельно от CI; existing guard требует CI для SUCCESS; producer и whole-report consumer различают point-only и interval | G01 real backend/native custody; G03 inferential/scientific validity |
| B213 | Requested estimand был только подписью | Legacy constructor/identify связывает estimand и отказывает при обнаруженном mismatch; selected worker имеет точный allowlist, bound rows/graph/parameters и проверку effective reply; consumer сверяет весь report | G01 actual API execution; G02 legacy/NIE и внепрофильные запросы; G03 assumptions |

Полная карточка 6691–6782 прочитана. Source/test/config/dependency edits и установки не выполнялись. Отсутствие более общего estimator не объявлено дефектом при честном ограничении профиля.

## 2. B212: useful partial result сохранён, неопределённость не выдумана

Legacy adapter отдельно извлекает point, SE и supported interval. Нет CI — `build_failure_report` получает finite point, реальный доступный SE и `confidence_level=None`, metadata `point_only`; настоящий CI идёт в success path. [S01:350–426](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/dowhy_identify_estimate.py#L350-L426)

Selected `report_from_worker_result` строит тот же полный canonical report из уже проверенного worker reply. Interval=None сохраняет point и возвращает `NUMERICAL_FAILURE`; interval есть — используются его endpoints и подтверждённый уровень95%. Projection сам не запускает backend и не является source admission. [S01:574–630](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/dowhy_identify_estimate.py#L574-L630)

**P01:** пять исходных recorder tests исполнены с actual adapter/Graph/Report AST: point7 безCI, interval[5,9], forwarding NIE, mismatch ATE-vs-NIE, неизвестный estimand до dependency load. Recorder — не DoWhy и не доказательство numerical NIE. **P06:** selected synthetic reply проходит actual validator, point-only и interval проходят actual Pydantic JSON roundtrip.

`CausalEffectReport` по-прежнему требует point+CI для SUCCESS. Failure envelope имеет широкий heuristic sentinel range, level=None и gate_eligible=False; это видимость partial result, **не CI и не оценка дисперсии**. Success causal report тоже не получает causal-identification authority автоматически. В C55 исполнен actual projection body, но envelope constructor — fixture; полный native ABI остаётся G01. [S07:598–709](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal.py#L598-L709)

## 3. B213: выбранный owner, а не совпадение labels

Default adapter проверяет requested estimand/method/contrast/target/level и typed GraphCausalData до worker. Вне точного профиля — `INPUT_INVALID` с capability `unsupported_worker_profile`; отсутствие source context — `NUMERICAL_FAILURE/backend_unavailable`, без point/backend witness. **P03:** шесть unsupported requests и no-context control подтверждены. [S01:429–531](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/dowhy_identify_estimate.py#L429-L531)

Реальный standalone source передаёт estimand в `CausalModel`, вызывает identify с `proceed_when_unidentifiable=False`, требует backdoor identification и ровно заявленный adjustment set. Перед estimate проверяет binary treatment и full-rank design. В estimate явно переданы control0, treatment1, target ate, no effect modifiers, confidence_intervals=True и confidence_level=.95; затем проверяется actual estimator level и CI запрашивается явно на .95. [S03:69–151](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/workers/dowhy-014/worker.py#L69-L151)

Это **прочитанный реальный owner**, но его DoWhy numerical body в C55 не исполнялся. Version lock и README не превращены в runtime proof. Имеющиеся tests действительно предусматривают actual DoWhy vs independent Statsmodels и 200 independent synthetic repetitions, но здесь они UNRUN. [S12:72–122](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/workers/dowhy-014/tests/test_worker.py#L72-L122)

## 4. Producer → bridge → actual consumer

Parent source context загружает actual CAS bytes/manifest и typed contract. `_bound_request` сравнивает полный materialized input с восстановленным source, связывает matrix/columns/common row IDs/graph/parameters/seed и request hashes. **P04** исполняет сам binding с явным in-memory context fixture: перестановка только outcome rows отвергается до запуска; strict standalone protocol принимает исходный aligned request. **CAS admission не исполнялась.** [S02:64–92](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/_dowhy_worker.py#L64-L92) [S02:250–299](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/_dowhy_worker.py#L250-L299)

Bridge проверяет exact reply fields, source/request/data/rows/graph, selected installed distribution inventory, effective estimand/method/contrast/target/adjustment и actual estimator class. Numeric primitives не допускают bool/string coercion; CI должен быть finite, ordered, содержать actual point и соответствовать95%; point-only не может утверждать level. **P05:** 46 malformed/missing-field/content mutations отвергнуты actual validator. Positive response — synthetic protocol fixture, его version labels не означают observed installation. [S02:146–247](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/_dowhy_worker.py#L146-L247)

Outer Scientist job связывает source с job, читает persisted result, сверяет offered report/envelope, переоткрывает bound source и проверяет worker identity. Затем `_verify_dowhy_worker_projection` заново строит **весь** expected report через canonical producer, а не сравнивает только point/interval. Outer lifecycle прочитан, не запущен. [S08:462–536](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py#L462-L536) [S08:582–615](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py#L582-L615)

**P06/P07:** actual complete-report verifier принимает canonical JSON roundtrip и отвергает восемь отдельных изменений: point, SE, interval, p-value, method_params/target, metadata authority, invented diagnostic и identified estimand. Forged epsilon-CI на point-only также отвергается. Это отличает содержательный producer→consumer control от двух одинаково подписанных peer objects. Source revalidation всё равно обязательна и не заменяется этим сравнением.

## 5. Сохраняемый результат и точные G

- **Сохранить:** partial point, отсутствие fabricated CI/zero SE, общий SUCCESS guard, точный selected profile, explicit refusals, actual source/reply binding, full-report projection, non-gating candidate output.
- **C55-G01:** выполнить existing non-skipping real worker/Statsmodels oracle и parent Python3.14 native job/CAS/fresh-reader tests в поддержанных средах. Сейчас pytest/DoWhy/Statsmodels и frozen worker environment отсутствуют; ordinary application import блокируется Python3.14 syntax under3.12. Никаких установок не было.
- **C55-G02:** legacy-inprocess не равен selected production backend. Он передаёт estimand, но не всю contrast/target/level semantics в estimate call. Recorder NIE не доказывает actual NIE API/capability. Current selected path честно отказывает вне ATE/0→1/ate/.95; не требуется притворяться универсальным. Migration/FQN вопрос отдельно продолжится CAU-05.
- **C55-G03:** neither content hashes nor successful numerical output establish graph correctness, identification, positivity, IID/constant-effect/Gaussian validity or real-data coverage. Synthetic fixture здесь вообще не numerical backend witness. LLM может предлагать causal structure, но это не empirical authority.

13 unchanged bodies/24 cases: legacy recorder5/5, standalone numeric/protocol4/10, parent asset/allowlist/no-context4/9. Native test bodies не заменены fake CAS. Две ошибки внешнего audit harness сохранены отдельно (module namespace и test alias), исправлялся только probe. Финальный probe exit0, Git clean.

[Диагностика](../04_Проверки/C55_CAU04/bounded_diagnostics.json) · [Команды](../04_Проверки/C55_CAU04/commands.json) · [Границы](../04_Проверки/C55_CAU04/native_verification.json) · [Источники](../05_Источники/C55_источники.json) · [Остатки](../01_Реестры/C55_остатки.json).

**55/127 пакетов рассмотрены ограниченно; 132 уникальных B/LA частично оценены. Следующий — CAU-05. Полного закрытия нет.**
