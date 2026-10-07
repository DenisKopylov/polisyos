Current delta instructions: [latest E actions](../../integration/reviews/E-next-wave-2026-10-06.md). For E also use [PR38 r2 continuation](E-resume-after-pr38-r2.md). Apply historical tasks below only to the still-unresolved original criterion; do not repeat already-measured unchanged source.

# E — продолжение PR38 после независимого разбора G

Продолжай E02 как облачный оркестратор E. Заверши доступные code/mechanism, verification и default-consumer остатки, публикуя законченные slices по готовности. Доведи весь набор из 22 bundles / 54 findings до решений по исходным критериям и конкретных owner handoffs. Реализуемый bridge, ошибочная математика или отсутствующий положительный witness требуют работы. Внешний input/решение должен иметь точного владельца, минимальные входы и следующий проверяемый результат. G принимает код отдельно от finding closure.

## Начало и обязательные источники

Полностью прочитай корневой `AGENTS.md`, `policy-engine/CONTRIBUTING.md`, `policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/HANDOFF.md`, failure/repair register и execution-organization README. В этом E02 каталоге прочитай `closure-decisions/{README.md,E.md,method-decisions.md,semantic-decisions.md,coverage.json}` и `integration/reviews/E-pr38-continuation-audit-2026-10-06.md` из fetched G ветки. Полные owner TSV и original cards определяют owner/criterion; короткая query не задаёт ownership. Исходный E.md остаётся полным планом всех bundles; этот prompt уточняет реальные остатки после нового результата.

Возобновляемый [PR38](https://github.com/DenisKopylov/polisyos/pull/38): branch `codex/e02-E-continuation-20261006`, последний проверенный head `be947056728a24d50432d32fbb9feabee7dfeffc`. Предыдущий frozen source `58e2d97965c0826c44843a78dcb2f8698d9950a3`, tree `ffd0d56892f8e515838af4c5b160cb9ac6d988ed`, base `198076863e143dea9f89f02734b13d50dae3eed5`.

Сначала `git status -sb`, HEAD/tree, fresh fetch и remote readback. Сверь состояние с последним собственным и проверь admission точной branch/path. Используй прежний admitted checkout; если облачная среда новая — возобнови его от fetched E head штатным способом, сохранив историю. Не делай reset/rebase/force-push или переключение, скрывающее текущую работу. SHA выше — identity разобранного результата, а не приказ вернуть более новый checkout к старому состоянию.

Fetch `origin/main` и `origin/codex/e02-integration`, прочитай последние G checkpoint/review. Checkpoint09 опубликован на `8ed2c08a96173a1235b4fc363fcbe07378a47750` и содержит принятые budget/callback/Lex slices. На clean boundary включи требуемый свежий G checkpoint обычным append-only merge; конфликт верни canonical owner. E root публикует свою topic/PR38; G — единственный integration publisher. В integration/main не пиши.

До использования results выполни importer:

```sh
python3 policy-engine/docs/research/e02-cloud-test-plan/results/import_results.py --check
```

После PASS прочитай `policy-engine/docs/research/e02-cloud-test-plan/results/verification.json`, затем выполни query:

```sh
python3 policy-engine/docs/research/e02-cloud-test-plan/results/query.py --unit E --failures-only --limit 30
```

Дальше делай точные queries каждого нужного ID/cell и читай полный criterion. Результаты baseline не являются PASS твоего нового кандидата.

Полный handoff находится на E head в `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/continuation-20261006/`: `README.md`, `final-handoff.json`, `closure-frozen/all-54-closeout.json`, `closure-frozen/local-G-closeout-recipes.json`, `consumer-frozen/source-trace.json`, `common-wave/*`, `final-closeout-review/*`. Saved wave: 1 123 PASS / 2 FAIL, ledger: 49 partial / 4 held / 1 closed. Из 33 bounded proposals B198 уже closed: 32 partial предложения требуют индивидуальной owner приёмки; ещё 17 partial имеют активный остаток. Held: B194/B197/B201/B202. Сохрани эти различия.

## Параллельная работа и границы writers

Масштабируй прямых helpers по готовой очереди до 20: независимые механизмы CAL, MC/UQS, DoE, BKT, PCL, DDM/FRC companions; отдельно oracle/review, imports/facades, evidence/criteria и dependencies. Один writer на общий механизм/файл/schema/facade/test/generator; один уровень delegation, без детей. Reviewer не автор проверяемого кода. Давай exact base, write paths или read-only режим и конкретный результат. Используй существующие admitted leaf checkouts, не размножай среды или одинаковые исследования ради слотов.

В cloud готовые численные проверки стартуют без искусственных квот процессов/threads/CPU. Сериализуй только shared DB/port/artifact writer. G координирует локальные A/C/G heavy checks; этот предел не переносится в облако.

A — writer `runtime/quality/generation_cycle.py` и HTTP `run_lifecycle.py`; C — `fabric/data_plane/streaming.py`; B — durable ledger; D — default Search/autotune consumer. Core/IR/public-surface owners согласуют shared facade/schema изменения. Для чужого seam подготовь typed contract, применимый patch/test packet и tracked dependency, продолжая свободную E работу. Не отправляй сообщения в чужие пользовательские чаты без прямой авторизации человека; Git handoff достаточен для обязательной координации.

## 1. Исправь математический остаток через существующие owners

**MC joint law, B188/B192.** Frozen source сохраняет ранее проверенные blobs. Weights `[.5,.5]` и `[.5000000000005,.4999999999995]` считаются равными по `atol=1e-12`, затем используется только первый вектор. `clip(U,1e-10,1-1e-10)` теряет допустимые крайние atoms с массой 5e-11. Выбери одну каноническую admitted representation weights; общий paired law должен точно согласоваться в ней. Каждая positive CDF category сохраняется либо выдаётся typed refusal при collapse/неоднозначном law.

Reuse NumPy/SciPy: для U∈[0,1) inverse-CDF buckets через `searchsorted(..., side="right")` без epsilon clip. Invalid/boundary U, zero weights и rounding обработай явно. Не обещай exact arbitrary-real law на конечной сетке; approximation law требует явной семантики. Новая библиотека или copula engine для корректного отказа unsupported law не нужны.

Admission поддержанного joint law выполняется **до stochastic draws и stochastic evaluator callbacks**. Два Uniform[0,1] с covariance diagonal 1/12 не устанавливают поддержанный joint law. Такой путь не должен выполнять стохастическую propagation или выдавать interval/authority/gate eligibility; положительные Gaussian full-covariance/nullspace и paired empirical controls сохраняются. Детерминированные nominal/gradient diagnostics допускаются как явно limited candidate при неизвестном joint law, с сохранением limitation и нулём stochastic attempts. Исходный B188 не задаёт общего veto на любой deterministic callback: не требуй `callback_count=0` для всего Node без отдельного criterion. Если конкретный API обещает pre-callback refusal, проверяй это обещание отдельно. Исправь общий inlet/transform и siblings, а не по одному backend-local исключению.

Сначала falsifiers на старом exact source, затем на новом candidate: tiny first/interior/last positive atoms, zero mass, U=0/1 и соседние CDF boundaries, почти равные разные weights, CDF collapse, переставленные paired rows, подставленный старый digest. Независимый dyadic fixture: rows (a,b)=(0,0),(1,2),(4,5), masses 1:1:2; y=a+b имеет mean 5.25, variance 15.1875. Unscrambled complete 256-net даёт 64/64/128 actual callback rows. Ожидания выводятся отдельно из law, не из того же results loop.

**CAL.** Воспроизведи новый статический контрпример `gaussian_observation_std={target: True}` и `numpy.bool_(True)` через настоящий `Calibrator.run`. Сейчас bool проходит positive-finite guard как 1, а `parameter_loader` вызывается до guard. Если probe подтверждает это, общий pure preflight должен исключать bool, принимать supported finite positive real scalars и работать до loader/emitter. Target-ID/join проверки выполняй в нужном контексте отдельно. Сохрани float positive, zero/nonfinite negatives и actual loader counter. Не повторяй unchanged scalar/batch JAX/Hessian wave без изменённой dependency. Raw curvature и неизвестный noise law не дают covariance authority; B197 source join/fit/consumer остаётся отдельной задачей.

**DoE.** Оставь locked SALib 1.5.2. На real sampler/analyzer добавь независимый interaction oracle: x,z iid U[0,1], y=x+z+2xz; S1=(12/25,12/25), S2=1/25, ST=(13/25,13/25), с объявленной numerical tolerance. Current interaction test проверяет list/tuple shape. Morris whole trajectories и unit-rescaling `(20,3)` уже имеют независимые tests — reuse их. Для replay меняй порядок целых valid blocks вместе с paired outputs: estimands сохраняются, content/order identity меняется, старый receipt отвергается. Samples-only mutation не является order-only oracle. Default Search доводит D; E выдаёт artifact/reader/negative packet, не второй search runtime.

## 2. Доведи настоящие default consumers

**BKT B166/B169/B170 — один класс default replay bridge.** Adapter меняет только outer masked DataSnapshotRef, Trinity ModelSpec остаётся unmasked. Requested seed хранится в ExperimentState.params, фактический FoundryExecConfig получает default seed=0. Generic `foundry.metrics` содержит executor counters, а не target/horizon forecast. С canonical workflow/input-binding/execution owners выбери реальную quantity и существующий producer: predictive ETS ForecastOwner либо typed simulation target trajectory с собственным purpose. Не превращай effect/scalar/count в forecast и не ослабляй strict binding.

Reuse CAS/DataSnapshot/Trinity/ModelSpec/materializer/DefaultFoundry: immutable replay snapshot + matching model binding, source/mask lineage, effective per-run ExecConfig.seed и consumed typed target/unit/time/horizon output. Сделай real positive K witness через заявленный native boundary. Основой может быть tiny fixture `tests/unit/scientist/orchestration/workflows/test_engine_default_workflow_e1_7.py` относительно `policy-engine/`. Выбор quantity/producer сверяется с original criterion: ETS не заменяет required native Foundry execution. Fixture доказывает generic wiring, а не фактическую production history.

Fresh reopen BacktestReport должен показать requested=attempted=completed=K, failed=0, различные actual seeds/run IDs, отсутствие fallback, exact masked row IDs/refs и consumed forecast refs. Negatives: missing/mismatched Trinity, future/leaky row, wrong target/horizon, spy, который возвращает counters в обход Foundry. Exact local history recipe выполнит G позже read-only; generic positive bridge не откладывай из-за отсутствия production dataset в cloud.

**PCL LA-052/053.** Три actual Foundry `_summarize_interval_diagnostics` calls не передают optional `calibration_store`. Проведи существующий configured CAS через method execution к persistence/readback и actual result refs; сохрани `gate_eligible=false`. Через fresh store независимо пересчитай requested/eligible/observed pairs: 95/100, 0/100, zero pairs, missing/reordered pairs и integrity-valid forged counts. Positional pairing не доказывает source identity; row/time/split binding получает producer там, где этого требует criterion. Alias остаётся до согласованного обоими API owners compatibility window. Новый periodic monitoring service для этого finding не нужен.

**FRC B32/LA-051 и A.** Первый FRC01 FAIL использует fake/unresolved refs и времена, нарушающие текущий contract. Подготовь настоящий synthetic CAS positive с correct manifest/time roles либо negative-refusal witness. A не должен принимать фиктивный mapping ради PASS. Второй FAIL показывает разные status sources в grade и S6 limitations. A нормализует один typed/recomputed status/reason: missing ref отдельно, resolved limited evidence отдельно. Нельзя требовать `insufficient-history` для любого missing ref. Передай A применимый test/contract packet через Git/G checkpoint; canonical writer не означает установленную атрибуцию причины red по P41.

E обеспечивает actual unit/scale, source schema resolution, независимый oracle fresh source rows→persisted intervals и совместимый field adapter `empirical_evidence_ref`/`candidate_receipt_ref` → A fields/rule/time roles. A самостоятельно resolve/bind/recomputes profile/source/metric/unit/split/horizon/pairs/counts/threshold/purpose/six roles в configured CAS, сохраняет собственный verifier provenance и проверяет fresh default/HTTP read. `credible=True` и producer receipt не trusted verifier. Сохрани terminal causal/treatment/policy refusal; A shared files самостоятельно не редактируй.

## 3. Доведи схемы, imports и пакеты внешних решений

**DDM.** Same closed `$id` + четыре optional fields несовместимы с old strict reader. В `ddm/integration/model_registry.py` и его `model_registry_record.schema.json` с owner зафиксируй directional reader matrix/version/migration: actual new producer→old reader, old record→new reader, fresh rebind/veto. Release fragment должен соответствовать actual internal classification. Current feed completeness, R2 signoff/deployment purpose и freshness требуют реальных входов/решения, не boolean/пустого trigger list. Library consistency и institutional authority имеют разные verdicts.

**12 E imports.** Reconcile AST slice-base→new source и exact edge list из G аудита. 35 changed-path rows / 163 total — другой знаменатель. Используй existing Core artifacts/canon, IR analytics, Calibration root и Foundry uncertainty facades. В owned facades добавляй только нужные typed exports и behavioral API/consumer tests. Core/IR owner выбирает admission existing sub-facade либо narrow root re-export; public contract/docs/inventory требуют его lease/review. Не копируй CAS/codec и не расширяй baseline/exceptions ради green. Прогони architecture guard после реального fix; остальные rows получают собственную owner attribution.

A/G и generator owners разбирают OpenAPI confidence projection 1 489→1 492, FeedbackSolveResult schema/_manifest и trust-posture. E передаёт source/affected contract packet; generated files не hand-edit. Static invocation 11 regressions / 42 new unresolved — ограниченный proxy: дай actual caller/persisted witness или точную unmeasured boundary; dummy calls не решение. Global red не inherited по пересечению лишь reported paths: нужны exact command на slice-base и полный input denominator. Свои math/import/bridge работы продолжай параллельно.

**Evidence.** Исправь summary 15→actual 21 workspace lint rows / 17 paths и все связанные hash/size refs. Final review summary row 20 087 bytes / hash 9681007… устарела; current 20 312 / hash `0ce085869713eb80540d088ece417ef1d116c5daabe28dc95446779d4d2a772b` совпадает с copy-index. Сохрани original stdout/history; новая corrective receipt различает historical и current publication. После исправления summary её hash снова пересчитывается. Не коммить повторный 171 MB raw dump: большие raw идут под ignored raw, в Git — умеренные deciding outputs и точные input/source refs.

**IR B201/B202.** Назначение canonical IR semantic owner должно быть явным. Подготовь reviewable пакет с вариантами/compatibility/consumer impacts:

1. Identification set и statistical uncertainty остаются отдельными linked artifacts. У summary независимые named point/interval functionals; mean не обязан лежать в equal-tail interval. Укажи atoms/asymmetry/weights/quantile conventions, unit/estimand admission и invalid-value отказы.
2. Новая семантика получает distinct v2 `$id`; v1.1 reader/replay не переписывается.
3. Exact joint carrier сохраняет axis/order/shared draw identity/weights/units и source/model/fit/rule/time/purpose lineage через content-bound CAS.
4. Owner выбирает CAS-only v2 (рекомендация опубликованного плана) либо inline carrier + persisted ref и назначает реальные consumers. Display summary отличается от обещания новых law-dependent computations; без resolved law такой computation отказывает, а не восстанавливает law из moments.

После ratification E реализует producer→CAS→sampler и packet для C/F consumers. Independent oracles: 99 zeros + 100 дают mean=1, q05/q95=[0,0], без расширения interval к mean; одинаковые summaries разных laws и paired correlation +1/−1 должны различаться после serialize/reopen. E/G не ратифицируют semantics кодом. Held B194/B197/B201/B202 не блокируют независимые E slices и не снимаются флагом.

## 4. Все findings, finished slices и closeout

По каждому из 54 ID обнови решение по original card в существующем ledger/closeout, не создавая 54 повторных планов. Укажи real producer/artifact/bridge/consumer/surface, exact oracle/negative output, basis каждого gate predicate, остаток code/input/semantic decision, owner и следующий конкретный результат. 32 partial proposals рассматривает accountable owner индивидуально. Новые code defects и missing default bridges не прячутся за старым label limited. Сохраняй дополнительные owner зависимости B172/B173 trust profile/equivalence, B190/B193 evaluator/result law/stopping assumptions, B200 information-unit lineage, B197 source fit/legacy consumer и DDM current-feed/R2 inputs из полного E.md и local recipes. B198 closed сохраняется.

Публикуй законченный slice рано: original implementation commits, затем отдельный committed `implementation-handoffs/E/<slice>.json` с base/candidate/tree, полным footprint/companions, runtime property, independent oracle, removal/adversarial controls, complete moderate outputs/env/input identity и limitations/next owner. Fetch/readback exact remote; attach PR38/новые PR штатным tool, если доступен. Push append-only в свою E topic. Новые commits требуют delta/dependency/evidence review; unchanged часть прежнего review reuse. Commit на clean boundaries; stash не место хранения работы.

В iteration запускай affected family/importer/consumer checks, Ruff/format, recomputing validators с corrupt-field negative и architecture boundaries. После source freeze и **всех независимых reviews** проведи один common numeric/gate wave на этом SHA. Повтори ранее UNRUN umbrella stages после устранения fail-fast причин. Cosmetic post-freeze debt записывается; blockers собираются в batch перед следующим freeze. Browser уже проходил doctor; это не full CI PASS. Не ослабляй required checks и не push main.

Production data остаётся локально read-only; G получает minimal immutable inputs конкретной recipe только там, где criterion зависит от фактической history/law. Generic properties принимаются по достаточному native fixture. Отсутствующий source input не заменяется выдуманным authority-positive fixture.

Конечный handoff различает выполненные E fixes/default witnesses, owner-ready A/D/Core/IR/G packets, proposed/accepted finding decisions, unavailable inputs, skipped backends, UNRUN stages и remaining verification по всему набору. Внешний HOLD не останавливает свободные работы. Если нужно новое human input/ratification, сначала дай concrete reviewable packet с вариантами/ценой.

Код, полезные docs и уникальные данные сохраняй. Использованные повторимые fixtures/overlays перемещаются только в native Trash после deciding receipts и проверки отсутствия active users. В cloud без Trash лишь перечисляй candidates. Trash не очищай; постоянное удаление запрещено.

Pattern pass P01/P02, P04/P05/P09, P07/P08, P10/P14, P27/P31, P29/P32/P33, P35/P36, P37/P38, P40/P41: проверяй runtime property и источник predicate, исправляй класс и сохраняй точную base/red provenance. Число PASS и наличие полей не являются самостоятельным критерием завершения.
