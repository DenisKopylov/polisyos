# E PR38: независимый разбор и задачи продолжения

E выполнил значительный объём численной работы и persistence/readback. Продолжение требует исправить конкретные математические условия, довести default consumers, заменить некорректный положительный FRC fixture и получить решения внешних владельцев. Готовый [промпт E](../../execution-prompts/continuation-2026-10-06/E-resume-after-pr38.md) разделяет эти задачи и задаёт проверяемый результат каждой.

Семь независимых помощников G проверили evidence, полный набор критериев, imports/gates, CAL/MC, DoE/DDM, BKT/PCL и FRC/A/IR. Это чтение immutable Git objects и сохранённых outputs; новых E numerical или production прогонов здесь не было. Статические контрпримеры ниже требуют воспроизведения на кандидате. E code acceptance остаётся **HOLD**; finding ledger этим документом не меняется.

## Входы и подтверждённый результат

- [Draft PR38](https://github.com/DenisKopylov/polisyos/pull/38), branch `codex/e02-E-continuation-20261006`: head `be947056728a24d50432d32fbb9feabee7dfeffc`, tree `51c67e8b4f400e6b22c28828bbe1e5aeb6abdd4d`.
- Frozen source `58e2d97965c0826c44843a78dcb2f8698d9950a3`, tree `ffd0d56892f8e515838af4c5b160cb9ac6d988ed`; base `198076863e143dea9f89f02734b13d50dae3eed5`.
- Между source и receipt head source/tests не менялись. Полный набор 6 198 tracked paths под `policy-engine/src/` и `policy-engine/tests/` даёт framed SHA256 `9f8a51ddde321609d106d7ee7d747bde6a3182b7cc6747e1254d344e2ebd85fc`.
- Полный base→source footprint: 331 path — 44 src, 36 tests, 239 docs/tooling, 12 release fragments. E head не включён автоматически в G checkpoint09.

Первичные источники читаются через `git show <head>:<path>`. Корень E evidence: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/continuation-20261006/`. На указанном head прочитаны `README.md`, `final-handoff.json`, `closure-frozen/all-54-closeout.json`, `closure-frozen/local-G-closeout-recipes.json`, `consumer-frozen/source-trace.json`, все шесть XML/команд/receipts в `common-wave/` и `final-closeout-review/review-58e2d97965c0.json`.

Пересчёт всех шести JUnit XML и command arrays даёт 110 различных test paths, 1 125 уникальных `(classname, name)` cases: **1 123 PASS / 2 FAIL / 0 ERROR / 0 SKIP**. По группам: CAL 266, MC 297, DoE 119, PCL 89, DDM 71, BKT/FRC 281 PASS и 2 FAIL. Все 41 blob из `common-wave/copy-index.json` совпали по hash/size. Из девяти global checks семь FAIL, два PASS — Ruff и format. После fail-fast остаются UNRUN части backend/CI wave и отдельный Atlas gate.

Полный closeout JSON содержит 54 finding ID, 22 bundle и 55 ID-to-bundle links: LA-051 принадлежит обоим FRC bundles. Ledger: **49 partial / 4 held / 1 closed**; verdict: **49 limited / 4 held / 1 closed**. В 33 bounded-owner proposals уже входит closed B198, поэтому новых предложений по partial — 32; ещё 17 partial имеют активный остаток. Held: B194, B197, B201, B202. E labels «52 bounded mechanics GO + 2 semantic-held» не заменяют независимую приёмку этих условий.

| Полная группа ID | Bounded proposals, включая уже closed B198 | Остаток |
| --- | --- | --- |
| E1, 15 ID | B176–B185, B195, B196, B198, B203 | B197 held |
| E2, 13 ID | B186, B187, B189, B191, B199 | B188, B190, B192, B193, B200; B194/B201/B202 held |
| E3, 15 ID | B167, B168, B171, B174, B175, LA-056 | B166, B169, B170, B172, B173, LA-052–LA-055 |
| E4, 11 ID | B97, B98, B99, B101–B105 | B32, B100, LA-051 |

Знаменатели сверены по всем `rows` closeout JSON, всему `closure-decisions/coverage.json` и полным owner TSV. Original bundle cards определяют criterion; proposals не переводятся пакетно в closed.

## Два FRC FAIL требуют разных действий

Canonical writer A не означает, что оба FAIL доказывают ошибку production A. E не менял `generation_cycle.py` и `test_frc_01.py`; P41 остаётся `not_established` без достаточного exact-base replay и полного input denominator.

`test_calibration_time_roles_are_preserved_from_bound_evidence` передаёт raw mapping/`SimpleNamespace`, несвязанные outcome/evidence URI и выдуманный hash. Времена нарушают текущий contract. A создаёт record из resolved, content-bound `_S10ResolvedEmpiricalEvidence` с допустимыми шестью ролями. Отказ может быть правильным. Нужен настоящий synthetic CAS witness: producer→persist→fresh resolver→record, либо этот fixture становится negative. Сохранить fake-ref и bad-time отказы. Изменять temporal domain можно лишь отдельным решением владельца.

`test_missing_calibration_evidence_refs_stays_typed_blocked` показывает реальный reasonless downgrade private helper: grade блокируется аргументом `calibration_status`, а S6 limitations читают status из другого mapping, где его нет. A должен выводить статус и reason из одного validated typed основания. Отсутствующая ref даёт missing-ref reason; resolved limited evidence — свой reason. `insufficient-history` нельзя требовать для любого missing ref.

E→A field adapter также отсутствует: E возвращает `empirical_evidence_ref` и `candidate_receipt_ref`, A ожидает `empirical_calibration_evidence_ref`, `expected_rule_version_ref`, `temporal_roles`. Нужны общий configured CAS, recomputation source/metric/unit/split/horizon/rows/pairs/counts/rule/profile/purpose/time, собственный verifier provenance A и fresh served read. MetricKey не заменяет unit; DataSchema ref должна разрешаться. Oracle по тем же BacktestReport comparisons зависим: сверять fresh source rows с отдельно persisted intervals и известным ответом. E receipt не становится authority; predictive evidence сохраняет terminal causal/treatment/policy refusal.

## Механизмы, которые надо довести

| Семейство / ID | Реальное достижение | Следующее действие и discriminator |
| --- | --- | --- |
| CAL, B176–B185/B195–B198/B203 | Scalar/batch JAX, objective/cache identity, raw curvature, typed report→welfare | Статический новый случай: bool/np.bool_ допускаются как sigma=1, guard стоит после parameter_loader. Воспроизвести; общий finite-positive-real preflight до loader, float positive и loader counter. B197 source-row join/noise-law fit требует своего input/consumer. |
| MC/UQP, B186–B194 | Gaussian/nullspace, failed support, persisted denominator, pilot→fixed N | Один joint-law admission/transform: near-equal unequal weights подменяются первым вектором; epsilon clip теряет positive atoms 5e-11; Uniform + valid covariance вызывает nominal callback до unsupported-law ValueError. Typed refusal до callback; Gaussian/paired positives сохраняются. |
| UQS, B199–B202 | Duplicate-content controls, v1.1 replay, conditional carriers | CAL posterior→exact paired law→CAS→sampler; actual information-unit lineage. B201/B202 требуют appointed IR semantic owner. |
| BKT, B166–B175 | Denominators, numeric diagnostics, CV/bootstrap, K dispatch/refusal | Default positive K bridge: masked snapshot согласован с Trinity ModelSpec; requested seeds доходят до FoundryExecConfig; actual typed target/horizon output вместо generic foundry.metrics counters. |
| PCL, LA-052/053 | Pair persistence/recompute, fake-count rejection | Три actual Foundry summary calls не передают calibration_store. Провести существующий configured CAS через method execution и вернуть actual refs consumer-у. Alias compatibility решают оба API owners. |
| DoE, B97–B105 | SALib, Morris whole trajectories/unit rescale, CAS readback | Interaction oracle y=x+z+2xz для iid U[0,1]: S1=(12/25,12/25), S2=1/25, ST=(13/25,13/25). Current test проверяет форму. D доводит default Search consumer. |
| DDM, LA-054–LA-056 | Quantity/source reconciliation, expiry distinctions, JSON rebind/veto | Closed schema с тем же $id получила четыре optional fields; new→old strict read несовместим. Directional reader matrix/version/migration и internal classification; actual current feed/R2 signoff/deployment purpose от owner. |
| FRC, B32/LA-051 | ETS producer, отдельные CAS evidence/candidate | Actual unit/source/schema identity, независимый численный witness и A-owned default/verifier/served chain; исправление test contracts выше. |

MC/CAL/DoE/FRC relevant product blobs на freeze совпадают с ранее проверенными component candidates; DDM не менялся после своего candidate 052. Большой wave не исправляет перечисленные остатки. Перенос review касается только unchanged части. Morris geometric `(20,3)` oracle и whole-trajectory reorder уже существуют.

Для MC выбран минимальный путь: существующие NumPy/SciPy/JAX/IR owners, одна каноническая representation weights, проверка CDF representability и inverse CDF без epsilon clipping. Для U∈[0,1) `searchsorted(..., side="right")` задаёт полуоткрытые buckets ([NumPy 2.3 API](https://numpy.org/doc/2.3/reference/generated/numpy.searchsorted.html)). Collapsed/ambiguous law требует typed refusal либо явной approximation law; точный arbitrary-real law на конечной машине не обещается. Copula engine для корректного отказа unsupported covariance не нужен. Для DoE оставить locked SALib 1.5.2 и её [существующий analyzer](https://github.com/SALib/SALib/blob/v1.5.2/src/SALib/analyze/sobol.py). Новая библиотека или собственный sensitivity engine не закрывают missing oracle.

## Imports, gates и исправления evidence

AST base→candidate дал 12 новых cross-root module imports. Это отдельный знаменатель от 35 E-changed-path rows среди 163 architecture report rows.

| Source module | Новый target module |
| --- | --- |
| calibration.continuous | core.artifacts; core.canon |
| calibration.forecast_bridge | ir.analytics.forecasting_uncertainty |
| foundry.methods.catalog.econometrics.advanced | core.artifacts |
| foundry.uncertainty.sampling_admission | ir.analytics.uncertainty |
| scientist.methods.autotune.sensitivity_bridge | core.artifacts, TYPE_CHECKING |
| scientist.methods.backtesting.forecast_owner | calibration.forecast_bridge |
| scientist.methods.doe._receipt | core.artifacts; core.canon |
| scientist.methods.search.sensitivity_adapter | core.artifacts, TYPE_CHECKING |
| scientist.nodes.builtins.simulate.propagate_uncertainty | foundry.uncertainty.sampling_admission |
| scientist.nodes.builtins.simulate.propagate_welfare | foundry.uncertainty.sampling_admission |

Модули выше находятся под `policy-engine/src/polisyos/`. Core artifacts/canon уже имеют curated facades, но не признаны supported entrypoints. Их owner выбирает явное admission существующей facade или узкий root re-export. IR analytics, Calibration root и Foundry uncertainty уже дают reuse boundaries. Изменение public contract требует owner decision/lease, behavioral API tests и companions; baseline sync не исправляет границу. E правит свои callers/facades.

В `common-wave/summary.json` ошибочно указано 15 workspace lint violations; полный `workspace-verify-after-browser.stdout.txt` содержит **21 row / 17 paths**. В `final-closeout-review/review-58e2d97965c0.json` summary integrity row устарела: 20 087 bytes / hash `9681007…`, тогда как current summary — 20 312 bytes / hash `0ce085869713eb80540d088ece417ef1d116c5daabe28dc95446779d4d2a772b`. Copy-index совпадает с current blob. Исправить все связанные hash/size refs append-only, сохраняя исходный stdout. Saved publication e5bb — исторический; live head be947 подтверждён отдельным readback.

OpenAPI confidence projection/dependency count 1 489→1 492, FeedbackSolveResult schema/_manifest и trust-posture drift требуют A/G и canonical generator owners. Generated bytes не правятся вручную ради PASS. Global red не является inherited по пересечению только reported violation paths: нужны exact slice-base command и полный input denominator. Все 15 saved receipts сохраняют P41 `not_established`.

Static invocation checker даёт 11 regressions / 42 новых unresolved entries, но не наблюдает router/DI/callback/deferred runtime calls. Нужен actual caller/persisted witness либо точная limitation; dummy calls не доказательство. Browser после установки проходит doctor, но не снимает schema/import FAIL и не делает UNRUN стадии успешными. 171 MB raw diagnostic повторно не раздувался.

## Дальнейшая приёмка

E исправляет доступные code/mechanism residuals и выдаёт применимые пакеты A/D/Core/IR/G для внешних seams. Независимые работы продолжаются при одном held input. Проверять affected family/consumer и adversarial controls на exact candidate; общий wave один раз после freeze и всех reviews. Каждое из 32 proposals сверяется с original criterion отдельно. B198 сохраняется; held не снимаются флагом или synthetic fixture вместо необходимого owner input.

G ставит read-only local source/history checks лишь там, где это требует criterion. Dataset в cloud не нужен для generic wiring/math. G остаётся integrator, не E/A/IR producer. Публикация этого документа не разрешает push в main.

Pattern pass: P01/P02 — bridges; P04/P05/P09 — reason/status/purpose; P07/P08 — seed/time/version; P10/P14 — независимость math/source; P27/P31 — canonical owners; P29/P32/P33/P37/P38 — real runtime и fake-premise controls; P35 — полный набор; P40 — исправление класса joint-law/default-bridge; P41 — exact-base provenance.
