# Численные методы: решения, которые должны дать функцию

Goal: восстановить математически корректную поддержанную функцию на canonical
owner, сохранить provenance и consumer semantics, уменьшить цену сопровождения.
Ни библиотека, ни валидный DTO сами по себе не устанавливают admissibility.

## Уже проверенные методологические разграничения

| Свойство | Выбранное направление | Почему / проверка |
| --- | --- | --- |
| CAU-03/B210: robust bias correction в RDD | Native clean-room CCT sharp HC0 на sourcefb022aa; pinned rdrobust2.1.0 — реально выполненный development-only differential oracle. | RDD receipt15a checks0–5/12: native/CAS/consumer,4036 cases,2000 replicates per arm, retained-marker RBC removal. GPL product bundling отдельно и не блокирует native implementation; sharp fixed profile/real assumptions см. [F-M6](#f-m6). |
| BER-01/LA-036: conditional explanation | Bound conditional sampler over admitted source law; обычный KernelExplainer допустим только для объявленного replacement/marginal профиля. | Его documented background masking заменяет отсутствующие признаки значениями background rows. Это не общий conditional sampler при зависимых признаках. Контроль: correlated Gaussian, где conditional и replacement coalitions дают различные Shapley values. [KernelExplainer API](https://shap.readthedocs.io/en/stable/generated/shap.KernelExplainer.html). |
| UQ / Sobol low-discrepancy generation | Использовать уже доступный SciPy QMC и валидировать фактический sampling design; статистическую error estimate получать по корректным independent scrambles/репликациям. | `random_base2` сохраняет balance при 2^m; skip/thinning/arbitrary n могут лишать последовательность этого свойства. Это не запрет любых n, а запрет приписывать им гарантию balance. [SciPy Sobol](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.Sobol.html). |
| Causal estimation vs identification и interval inference | Расширять существующий typed causal owner, подключая выбранный estimator по его estimand/assumptions. | DoWhy разделяет model→identify→estimate→refute. EconML DRLearner задаёт cross-fitting и inference profiles; библиотечный вызов не подтверждает истинность causal graph и не делает каждый flexible learner CI достоверным. [DoWhy](https://arxiv.org/abs/2011.04216), [EconML DR](https://econml.azurewebsites.net/spec/estimation/dr.html). |

Таблица сохраняет proposed choices C–E; строка CAU-03/F выше обновлена по actual receipt. Для proposed профиля owner закрепляет backend version, actual parameters, dtype, source inputs, fit/split seeds, среду и полный runtime call; без них `UNRUN`/unsupported. Current F evidence и его границы приведены отдельно ниже, не как полный composed-product PASS.

## Что требуется от каждого окончательного method decision

1. Указать mathematical quantity (estimand, law, functional, support, confidence
   meaning) и случай расхождения текущего proxy с ней.
2. Сопоставить reuse-existing, maintained external implementation и минимальную
   correct own implementation. Выбрать вариант, а не закончить перечнем библиотек.
   Оценить действительные операции, интерфейс, deployment profile и сопровождение;
   API shape и “pip доступен” не являются проверкой runtime совместимости.
3. Реализовать выбранную функцию на существующем владельце, мигрировать default
   и non-test caller, сохранить persisted input/output identity и status/limitations.
4. Построить independent analytic/DGP/reference oracle с другой вычислительной
   логикой. Package-to-same-package comparison не даёт независимости.
   У stochastic coverage задать повторения, confidence tolerance и seed policy до run.
5. Для missing source law либо получить и связать реальный carrier, либо предложить
   конкретный supported producer profile. Marginal summaries не заменяют joint draws;
   диагностическое приближение не получает normative authority.


## Карта конкретных method decisions

Исторические решения C–E ниже выбраны для следующей реализации; их oracles — спецификации, не новые PASS. F-раздел обновлён source-bound receipts без scientific rerun. Детали deployment находятся в runtime-profiles; одинаковые источники закона и persisted поля следуют одному semantic решению.

<a id="methods-c"></a>

## C — выбранные методы

<a id="c-m1"></a>

### C-M1 — BERL conditional Shapley: verified Gaussian law, exact law / approximate MC expectations

**Выбранное решение.** Implement as a full conditional capability: verified joint-law binding -> supported conditional draw/expectation producer -> existing coalition/Shapley executor -> versioned persisted ExplanationBundle -> Runtime and Phase5 readback. The Gaussian conditional distribution is analytic; only coalition expectations with an analytic model oracle are exact. Finite draws for general nonlinear models are approximate Monte Carlo estimates with declared precision. Standard KernelExplainer is not the conditional sampler. Keep current diagnostic/refusal behavior until that path exists.

**Библиотека и собственная часть.** Reuse BERL's existing coalition enumeration and persist/readback contracts. SHAP KernelExplainer uses background rows to integrate out absent features; it does not infer P(X_not_S | X_S) from correlation. Own the small conditional Gaussian draw provider and feed its expectation into the existing executor; do not fork a second Shapley engine or treat a masker/dependence label as a law.

**Закон и область поддержки.** For a content-resolved, verifier-admitted source/model whose Gaussian family, feature variables/order, observed population/cohort, epoch/time, schema, and support all match this request, compute mu_notS|S = mu_notS + Sigma_notS,S Sigma_SS^+ (xS-muS) and Sigma_notS|S = Sigma_notS,notS - Sigma_notS,S Sigma_SS^+ Sigma_S,notS. A covariance matrix or normal-family label alone is not source/family admission. Validate finite values, symmetric PSD covariance, exact variable/order mapping, and xS in singular support; preserve null spaces and refuse inconsistent support rather than silently adding jitter. The conditional law is analytic; finite floating-point computations carry numerical tolerances.

**expectation_estimator.** For affine/linear f with an analytic coalition oracle, compute v(S) and Shapley values analytically, exact within floating-point tolerance. The first nonlinear certified profile uses fixed-N IID conditional draws for an independently admitted structurally bounded f in [a,b], for example a new content-bound tanh-output profile with a structurally verified bound; this profile is next implementation work, not an existing G97 registration. Freeze all K requested coalitions, epsilon and total delta before sampling; use N = ceil((b-a)^2 * log(2*K/delta) / (2*epsilon^2)) for each sampled coalition, and the Hoeffding intervals intersected with [a,b]. The K-coalition union guarantee is conditional on the admitted law/model and IID draws, not on arbitrary observed data. Exact Shapley enumeration consumes these coalition intervals by interval arithmetic; a coalition epsilon gives a per-coordinate error at most 2*epsilon, so choose epsilon = epsilon_phi/2 when that is the target. Record seed, N, K, bound-verification/profile refs, epsilon, delta and intervals; do not stop early from a fixed-N CI width. If a predeclared compute/draw cap is below required N, return precision_not_met and the honest achieved error bound; never silently shrink N or certify the requested tolerance. A declared bound, sample extrema or output clamp is not admission of the original model function. Arbitrary unbounded/unsupported nonlinear f may emit a predeclared fixed-N estimate and explicitly asymptotic diagnostic MCSE; it receives no certified precision_met/exact claim. Sequential stopping requires a separately implemented time-uniform confidence sequence or the independent-pilot/frozen-main contract in E; ordinary repeated-peek CI is unsupported. High-dimensional permutation sampling carries a separate error budget and is outside the first exact-enumeration profile.

**Основание fixed-N.** Для независимых ограниченных draws [a,b] Hoeffding даёт two-sided bound; union по заранее зафиксированным K coalitions даёт P(max_S |vhat(S)-v(S)| > epsilon) <= 2*K*exp(-2*N*epsilon^2/(b-a)^2) <= delta. Shapley weights sum to one, so two coalition errors bound one contribution by 2*epsilon. Это вывод для указанного supported profile, не результат runtime-прогона. [Первичная работа Hoeffding (1963)](https://www.tandfonline.com/doi/abs/10.1080/01621459.1963.10500830).

**Независимый oracle.** Exact analytic fixture: for (X1,X2)~N(0,[[1,.8],[.8,1]]), f(x)=x1, x=(1,1), conditional coalition values (0,1,.8,1) yield Shapley (.6,.4), with no Monte Carlo tolerance. At rho=0 conditional and marginal both yield (1,0). For a nonlinear f, compare finite-draw coalition estimates against an independent analytic or quadrature oracle under the same admitted law and assert the declared confidence/tolerance behavior, including a max-draw precision_not_met case.

**Negative controls.** Same correlated case through marginal-background KernelExplainer yields (1,0), so it must fail a conditional oracle despite matching field names and method label.; Reject changed law bytes/digest under the same caller ID, covariance without resolved source/model/population/epoch/verifier binding, wrong variable order/schema, asymmetric or materially indefinite covariance, impossible singular-support observation, stale model/population epoch, and absent law; do not fall back to marginal or independence.; For nonlinear f, remove bound/law admission while retaining metadata, substitute an unbounded function under the same declared [a,b], remove the frozen-N/union budget, or stop early using an ordinary CI; certified precision admission must fail. The independent bounded tanh fixture checks conditional expectations against quadrature and repeated-seed simultaneous coverage at the predeclared tolerance. Keep diagnostic MCSE, certified coalition error and permutation-sampling error distinct.; Reopen the persisted bundle in both actual consumers and remove the conditional producer while retaining metadata markers; the positive conditional gate must fail.

**Canonical runtime path.** policy-engine/src/polisyos/berl/service.py::ExplanationOrchestrator.explain; policy-engine/src/polisyos/berl/adapters/shap_kernel.py::KernelSHAPAdapter; policy-engine/src/polisyos/berl/contracts/explanation_bundle.py and contracts/schema.py; canonical bundle persistence/readback -> policy-engine/src/polisyos/runtime/quality/explanation_reliability.py::_validate_bundle_record; canonical bundle persistence/readback -> policy-engine/src/polisyos/scientist/validation/phase5_preflight.py::_run_berl_validation

**Основания.** **kind**: official_library_docs; **url**: [первичный источник](https://shap.readthedocs.io/en/stable/generated/shap.KernelExplainer.html); **supports**: Background data integrates out missing features by replacement; this API description does not establish conditional sampling.; **kind**: primary_method_paper; **url**: [первичный источник](https://arxiv.org/abs/1903.10464); **supports**: Conditional feature-attribution estimation under dependence requires an explicit conditional model/sampling approach.; **kind**: primary_method_paper; **url**: [первичный источник](https://proceedings.mlr.press/v119/sundararajan20b/sundararajan20b.pdf); **supports**: Shapley explanations depend on the chosen set function/game; distinct dependence semantics are not interchangeable.; **kind**: repository_source; **path_at_candidate**: policy-engine/src/polisyos/berl/adapters/shap_kernel.py@13946765e32ebd3a5da0f6a4eda5d90d74a8ad1e; **supports**: Current candidate's background replacement/coalition implementation and conditional diagnostic-only boundary.

**Сегодняшняя граница.** Capability incomplete until typed law producer/artifact, verifier, conditional-draw bridge, both readbacks, and a bounded user-facing attribution surface (or explicit surface_out_of_scope) are connected. No policy authority follows from an explanation.

<a id="c-m2"></a>

### C-M2 — BERL conditional Shapley: finite-support empirical profile

**Выбранное решение.** Implement as the second real supported conditional profile, consuming the same verified joint-law artifact owner and exact coalition executor. For each coalition, select only rows in the declared finite support matching the observed conditioning stratum and normalize their admitted weights. Empty or unsupported strata return a typed unsupported result.

**Библиотека и собственная часть.** Reuse E's aligned empirical-draw representation only after resolving its joint source identity and verifying same-row alignment/content; its current _EmpiricalJointSpec is internal UQP propagation machinery, not a BERL population law API. Do not use independent per-feature posterior draws, standard SHAP background replacement, kNN/kernel smoothing, or a new unconnected sampler service.

**oracle.** Small discrete joint table with nonuniform row weights: enumerate each coalition's matching rows, compute its weighted conditional mean independently by hand, and derive Shapley values from those coalition values. Permuting columns with a corresponding variable-ID permutation must preserve feature-labeled results.

**Negative controls.** Different joint_sample_id, sample_axis, sample count, row order/digest, or unequal aligned weights rejects the joint law even if each marginal carrier validates.; Empty exact stratum, continuous values without declared finite support, wrong population/time, or missing verified law yields typed unsupported; no marginal, smooth-density, or independence fallback.; Change one source row while retaining the caller label and recomputing only a superficial envelope; owner-level digest/readback must detect the changed law.

**Canonical runtime path.** policy-engine/src/polisyos/ir/analytics/uncertainty.py::PosteriorSamplesCarrier / DistributionCarrier; policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py::_build_empirical_joint_spec; verified law owner -> BERL conditional draw provider -> ExplanationOrchestrator.explain -> persisted ExplanationBundle -> Runtime explanation_reliability and Scientist phase5_preflight

**Основания.** **kind**: repository_source; **path_at_candidate**: policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py@5f9f4ae333cf13d152ae84693b44e73918b01703; **supports**: Existing aligned-sample-axis and shared-joint-id admission checks; current behavior remains internal to uncertainty propagation.; **kind**: primary_method_paper; **url**: [первичный источник](https://arxiv.org/abs/1903.10464); **supports**: Conditional expectations under dependent features require explicit conditional estimation, not an unconditioned background replacement.

**Сегодняшняя граница.** Finite exact strata only. Any continuous estimator or smoothing profile is a distinct method with its own fitted artifact, bandwidth/weights, uncertainty, and provenance; not part of this minimum profile.

<a id="c-m3"></a>

### C-M3 — Embedding generation and publication

**Выбранное решение.** Extend the canonical immutable-generation builder, source-basis builder, selector, and actual domain readers. Do not build a second vector-store generation system. Bind complete source membership plus the immutable encoder/model weights, tokenizer, normalization and output-affecting profile into the generation identity.

**Библиотека и собственная часть.** Reuse repository `build_embedding_generation` / `_build_embedding_generation_from_vectors`, `atomic_commit_path`, `resolve_embedding_generation`, and canonical catalog/academic consumers. A vector index library can store vectors but does not prove complete source membership, model identity, or which generation the consumer selected; those remain owner contract and readback duties.

**oracle.** Synthetic catalog snapshot ds-1 -> build and publish ds-2; resolve selected generation and query the real DatasetCatalogStore.search_by_vector, requiring ds-2 and the complete expected ID set. Inject failure before selector and require ds-1 remains readable; fail a legacy-alias write after selector and require actual readers still resolve ds-2.

**Negative controls.** Recompute internally consistent hashes after omitting or adding one source row; independent source membership reconciliation must reject the generation.; Keep model label constant and replace weights/tokenizer/normalization; model revision digest must invalidate the generation.; Remove/corrupt selector while files and markers remain; actual consumer must refuse rather than guess. Mutating a legacy flat alias must not change the selected immutable generation.; Withdraw one source fact and prove it no longer appears from the actual reader; entity-only evidence does not establish legal fact/provision membership or withdrawal.

**Canonical runtime path.** policy-engine/src/polisyos/data_forge/kernel/io/generation_basis.py; policy-engine/src/polisyos/data_forge/kernel/embeddings.py::build_embedding_generation / _publish_embedding_generation / resolve_embedding_generation; policy-engine/src/polisyos/data_forge/kernel/io/atomic.py::atomic_commit_path; policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/store.py::DatasetCatalogStore.search_by_vector (plus actual academic reader where selected)

**Основания.** **kind**: repository_source; **path_at_candidate**: policy-engine/src/polisyos/data_forge/kernel/embeddings.py@215c5f102eed26eb8079ed224b42d918dea1e8d4; **supports**: Staged immutable generation, inventory validation, selector publication, legacy alias ordering, and selected-generation resolver.; **kind**: repository_source; **path_at_candidate**: policy-engine/src/polisyos/data_forge/kernel/io/generation_basis.py@215c5f102eed26eb8079ed224b42d918dea1e8d4; **supports**: Current source ID/text/rule basis; extend to independently reconciled completeness and immutable encoder identity.; **kind**: repository_source; **path_at_candidate**: policy-engine/tests/unit/remediation/test_emb_02.py@215c5f102eed26eb8079ed224b42d918dea1e8d4; **supports**: Candidate generation publication/selector/reader witness; production-wide source membership and model identity remain unestablished.

**Сегодняшняя граница.** Prior selected generation remains readable on pre-selector failure; post-selector readers follow selector. Generation cleanup is a separate lifecycle and cannot precede live-reader movement.

<a id="c-m4"></a>

### C-M4 — Streaming retained-state cap, refusal, and restart restore

**Выбранное решение.** Reuse the current cursor/checkpoint/CAS path and preview the exact operator transition before committing an input chunk. Name the enforced limit max_retained_operator_rows/bytes. Preserve at-least-once-with-dedupe unless atomic source offset + state + output commit has proof.

**Библиотека и собственная часть.** Reuse existing StreamingWindowAccumulator transition, checkpoint/frontier, CursorStore, and FileSystemCAS; no substitute counter or separate queue/spill framework. The current preview measures retained operator state, not total process memory: source chunk, clean_rows, preview copy, emissions, and result-ref lists remain outside the cap; spill has no reader/consumer.

**oracle.** At exact retained-state capacity, accept the row that closes a window. On the next overflowing chunk, refuse before publishing its chunk/window/frontier; restore the prior committed checkpoint, raise cap, retry, and read back all ordered rows/windows with identical lineage and no silent loss.

**Negative controls.** Delete preview while keeping cap field/marker names; oversized retained state must then make the property test fail.; Crash-inject between chunk CAS, window CAS, prepared cursor/checkpoint, source commit, and committed marker; each restart must either replay with dedupe or fail closed on unresolved frontier.; One huge source chunk or output-ref list can exceed process memory while retained-state cap stays green; do not label this a total RSS/bounded-memory guarantee.; Never upgrade at-least-once-with-dedupe to exactly_once_narrow from a retry test alone; require atomic offset/state/output proof.

**Canonical runtime path.** policy-engine/src/polisyos/fabric/data_plane/streaming.py::_assert_rows_fit / process_stream_dataset / prepared-unresolved-committed frontier helpers; policy-engine/src/polisyos/fabric/data_plane/cursor_store.py and actual FileSystemCAS writer/readback; policy-engine/tests/unit/fabric/data_plane/test_streaming_capacity.py, test_streaming_runtime.py, test_streaming_windowed.py, test_cursor_store.py, test_processing_guarantees.py

**Основания.** **kind**: repository_design_decision; **path_at_candidate**: policy-engine/docs/adr/0133-fabric-streaming-scale-semantics.md@789e9e906cc52ff544fb05d4faa5db13359fee84; **supports**: Generic streaming is at-least-once-with-dedupe; exactly_once_narrow requires proof of atomic input-offset, state-update, and output-write commits.; **kind**: repository_source; **path_at_candidate**: policy-engine/src/polisyos/fabric/data_plane/streaming.py@789e9e906cc52ff544fb05d4faa5db13359fee84; **supports**: Candidate exact retained-row/byte preview and frontier restore implementation; it does not account for total run memory.; **kind**: repository_source; **path_at_candidate**: policy-engine/tests/unit/fabric/data_plane/test_streaming_capacity.py@789e9e906cc52ff544fb05d4faa5db13359fee84; **supports**: Candidate FileSystemCAS refusal/retry witness; crash-boundary coverage and total process-memory bound remain required limitations.

**Сегодняшняя граница.** Current evidence supports retained operator state only. A total-memory bound additionally needs pre-materialization source batch caps, incremental output persistence, bounded/paginated result references, and an actual spill consumer if spill is claimed.

<a id="methods-d"></a>

## D — выбранные методы

<a id="d-m1"></a>

### D-M1 — Bayesian search with fitted warm corpus, restart, and append conditioning

**Finding IDs.** OPT-03:B114; OPT-03:B115; CTL-02:B124; CTL-02:B125; CTL-02:B126

**Свойство.** A restored strategy predicts with the actually fitted model and transforms; compatible warm records are in train_X/train_Y before search; append-only observations preserve the same fit and do not trigger marginal-likelihood optimization.

**Сегодняшнее расхождение.** G97 validates warm parameter shape/range but does not recompute full compatibility; invalid outcomes are converted to a fabricated worst_valid+penalty response. Restore rebuilds a GP and loads state, but warm corpus/refit counters are not fully restored. Without an independent posterior oracle, state fields/replayed ask are proxies for predictive equivalence.

**Выбранная реализация.** Extend lazy optional BoTorch/GPyTorch SingleTaskGP. Full fit on initial/due/basis change; condition_on_observations only for same-basis append. Persist model/likelihood and transform states, effective space/objective/data identities, warm corpus/refit basis, local RNG, and policy/backend versions. Remove invalid pseudo-score from regression; represent feasibility separately if needed.

**Отвергнутый вариант.** Do not implement a new GP, silently create a default GP on restore, restandardize over the append batch, or replace the stack with sklearn/Ax/TPE absent a distinct measured need. Do not treat package-present as backend-ready.

**Canonical paths.** policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/scientist/methods/search/strategies/test_gp_resume_witness.py@e789e9523725fa081de5cdc69da5938489315b4a; policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/search-gp-continuation.json@origin/codex/e02-D-search

**Зависимости.** D-W01: OPT-03, CTL-02; actual G search consumer integration; optional torch/botorch/gpytorch runtime profile

**Положительная функция и независимый oracle.** The retained backend receipts establish mechanism only: warm rows in train_X/Y, restart/replay, append without marginal-likelihood refit, refit/corruption controls, RNG, and hard-limit resume. The existing witness compares BoTorch model.posterior paths to each other; it is not an independent mathematical posterior oracle. No analytic oracle receipt exists yet.

**Negative control и приёмка.** Add an unrun test to test_gp_resume_witness.py with 8–12 nondegenerate training points and held-out query points. Fit the real SingleTaskGP once, freeze its fitted mean/kernel/likelihood parameters and Normalize/Standardize state, then independently evaluate the selected fixture kernel and transforms and compute C=K(X,X)+σ²I; L=chol(C); alpha=solve(L.T,solve(L,y-m(X))); mu*=m(X*)+K(X*,X)alpha; V=solve(L,K(X,X*)); Sigma*=K(X*,X*)-V.T@V. Compare latent posterior mean and full covariance in original output units; test observation-noise prediction separately by explicitly adding query noise. Do not call model.posterior or condition_on_observations in the oracle. For append, concatenate X/Y and recompute under frozen parameters/transforms; compare to condition_on_observations. Count fits: initial=1, same-basis append/restore=0, due-refit/basis-change>0. Keep missing-state, changed-transform/corpus, and wrong-RNG negative controls, all rejecting before state mutation. Proposed only; no receipt.

**Границы.** Synthetic scalar GP and a fixed-parameter analytic oracle prove numerical mechanism for the selected kernel/noise/transform profile only, not calibration, production corpus, speedup, heteroskedastic models, device or all-platform behavior. Backend receipts remain bounded mechanism evidence; integrated G97 callers remain unestablished.

**Runtime.** **observed_profiles**: CPython 3.14.2; PyTorch 2.14.1+cu130; BoTorch 0.18.1; GPyTorch 1.15.2; CPU/Linux; CPython 3.14.7; PyTorch 2.10.0+cu128; BoTorch 0.16.1; GPyTorch 1.15.1; CPU/Linux; **optional_backend_absence**: UNRUN, never PASS

**Основания.** [первичный источник](https://botorch.org/docs/models); [первичный источник](https://botorch.org/docs/next/optimization); [первичный источник](https://docs.gpytorch.ai/en/v1.15.1/_modules/gpytorch/models/exact_gp.html); [первичный источник](https://botorch.readthedocs.io/en/latest/_modules/botorch/models/gpytorch.html#GPyTorchModel.condition_on_observations)

<a id="d-m2"></a>

### D-M2 — Typed scalar objective and canonical executable search actions

**Finding IDs.** OPT-01:B108; OPT-01:B109; OPT-01:B110; OPT-01:B111; OPT-02:B112; OPT-02:B113; OPT-02:B127

**Свойство.** Only finite, measured, correctly identified scalar outcomes enter GP/Pareto calculations; actual zero is distinct from absence. Pareto dominance is strict over fully bound coordinates, and the GP point is the actual effective action that can be executed.

**Сегодняшнее расхождение.** G97 creates a finite pseudo-observation for invalid outcomes. Presence/null/zero, NaN/Inf, metric/split/definition identity and candidate-vs-evaluation basis can collapse. Relaxed continuous vectors can quantize to the same integer/category action.

**Выбранная реализация.** Use the existing typed search owner and SearchSpace. Introduce a single admission boundary for objective states and effective-action decode/canonicalization; keep raw and direction-adjusted objective values plus definition/unit/split/version identity. Preserve intentional replicate IDs/seeds as separate observations.

**Отвергнутый вариант.** Do not substitute missing or invalid values with zero, epsilon, a generic penalty, or NaN ordering. Do not trust DTO markers, placeholder .5 coordinates, truncated IDs, metrics-as-parameters, or package import as proof of a wired backend.

**Canonical paths.** policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/src/polisyos/scientist/methods/search/; policy-engine/tests/unit/scientist/methods/search/strategies/test_effective_actions.py@origin/codex/e02-D-search; policy-engine/tests/unit/scientist/methods/search/test_objective.py@origin/codex/e02-D-search

**Зависимости.** D-W01: OPT-01/02; objective producer and real SearchSpace caller; evaluation ArtifactRef/data/split binding

**Положительная функция и независимый oracle.** D numerical oracle supplies independent Pareto/hypervolume and effective-action controls in candidate suites; owner reports 70 final search oracle passes and separate native/CAS controls. These are candidate-level receipts, not proof of integrated G97 callers.

**Negative control и приёмка.** Compare strict Pareto results with a slow independent comparator under input permutations, equal coordinates and mixed directions. Keep equal-valued distinct candidate IDs. Mutate missing/zero/conflict/nonfinite states independently. Decode two relaxed vectors mapping to one action and assert one search point unless explicit replicate ID; alter basis and assert no warm admission.

**Границы.** Numeric fixture coverage does not establish production objective ownership or all mixed/discrete space geometry. High-dimensional mixed optimization remains bounded; evaluate MixedSingleTaskGP separately if required.

**Runtime.** Use same pinned optional backend profile as GP decision; without working dependency/profile status is UNRUN.

**Основания.** policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/OPT-01.md@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/OPT-02.md@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/numerical-oracle-search-review.json@origin/codex/e02-D-oracle

<a id="d-m3"></a>

### D-M3 — Transfer: exact content admission and functional index generation

**Finding IDs.** TRN-01:B128; TRN-01:B130; TRN-01:B131; TRN-01:B132; TRN-02:B129; TRN-02:B133; TRN-02:B134; TRN-03:B135; TRN-03:B136; TRN-03:B137

**Свойство.** Warm data used numerically is resolved and content-bound to dataset/evaluator/model/scalarizer/split/search space/weights/replica basis and authorized owner. ANN is only bounded discovery. A reader sees exactly one complete immutable index generation.

**Сегодняшнее расхождение.** RunFingerprint omits dataset/evaluator/model/scalarizer/weight/vintage provenance and compatibility declarations self-attest; filtered top_k*2 can be partial. Existing FileSystemCAS and save_to_artifact already provide immutable artifacts and a composite ArtifactRef, but load_from_artifact assigns _dim, capacities, keys, metadata, key map and index separately, while query reads those fields separately. A concurrent query can therefore combine old/new in-memory state. There is no established external latest-generation pointer owner.

**Выбранная реализация.** Reuse FileSystemCAS immutable content-addressed artifacts and its composite vector-memory bundle ArtifactRef as the exact persisted generation identity. In VectorMemoryStore, build a complete frozen snapshot (dimension, native index, keys, metadata, key map, ref/version) off-path, then publish it with one in-memory snapshot-pointer swap. Each query captures that pointer once and uses only that snapshot. Apply the same publish rule to load and add/update. Do not add a second current-generation pointer in VectorMemoryStore. If a real external owner has a mutable latest pointer, name and update that owner instead.

**Отвергнутый вариант.** Do not infer numerical compatibility from ANN distance, IDs, field names or warm_start_compatibility strings. Do not call a filtered top_k*2 result 'best K'. Do not promote an in-process mutex/atomic rename into cross-process/distributed proof.

**Canonical paths.** policy-engine/src/polisyos/scientist/methods/autotune/; policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/scientist/methods/autotune/test_transfer_workflow.py@tree:de7d4f0a4e67f32dc26cb7182f8f1469a982094a; source-review-target@dabdd83fe235155a91dc6c7b1d85c7cfa5db6346; policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/transfer-numerical.json@origin/codex/e02-D-transfer; policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/transfer-generation.json@origin/codex/e02-D-transfer; policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/transfer-workflow-4097.json@origin/codex/e02-D-transfer; policy-engine/src/polisyos/core/artifacts/store.py@97c85fae:403; policy-engine/src/polisyos/scientist/agent/vector_memory.py@70b82ba9:160-256

**Зависимости.** D-W04: TRN-01/02; CAS content resolver and tenant/owner authority; SearchLoopRunner/GP consumer; generation writer and reader

**Положительная функция и независимый oracle.** transfer-numerical.json and later workflow source review remain bounded candidate evidence for real HNSW/FileSystemCAS, CAS-bound GP rows and wrong-origin zero admission/Sobol fallback; they do not establish atomic in-memory query publication, production provenance or G97 integration. No snapshot-race receipt exists.

**Negative control и приёмка.** Keep transfer admission markers but remove actual CAS resolve/hash/context checks; wrong-origin or altered basis must change admitted GP rows and fail. For TRN-02, barrier-interleave query with loading old/new bundles having distinct keys, coordinates and metadata, and with add/update publication; every returned key-distance-metadata tuple must belong wholly to one snapshot, never a mixture. A pinned composite ArtifactRef read in another process may prove immutable read consistency. Require multi-process latest-pointer/fault-injection tests only if an existing canonical owner actually publishes such a pointer; do not test or create a VectorMemoryStore pointer. These are proposed and unrun.

**Границы.** No production corpus or owner metadata; current numerical examples are synthetic. ANN filtering may return fewer than K admitted rows. Immutable CAS identity is available, but concurrent in-memory snapshot publication and production provenance remain unestablished; no distributed latest-pointer claim is made.

**Runtime.** Observed actual HNSW/FileSystemCAS paths on Python 3.14 candidate environments; exact production store/runtime profile not established.

**Основания.** policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/transfer-numerical-checks.txt@origin/codex/e02-D-transfer; policy-engine/tests/unit/scientist/methods/autotune/test_transfer_workflow.py@de7d4f0a4e67f32dc26cb7182f8f1469a982094a; policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/transfer-final-independent-review.json@origin/codex/e02-D-transfer

<a id="d-m4"></a>

### D-M4 — Funnel continuation and authoritative resource charging

**Finding IDs.** FUN-01:B156; FUN-01:B158; FUN-01:B159; FUN-02:B157; FUN-02:B160; FUN-02:B162; FUN-02:B165; FUN-03:B161; FUN-03:B163; FUN-03:B164; CTL-01:B118; CTL-01:B119; CTL-03:B120; CTL-03:B121; CTL-03:B123

**Свойство.** Continuation only follows a newly bound condition; empty/unmeasured/zero/invalid interval remain distinct. Stage verdict and aggregate verdict are separate. A budget charge exists only when the authoritative owner ledger debits it for the bound run/candidate.

**Сегодняшнее расхождение.** Trace stage cost=1 while BudgetState.spent={} and remaining=5. FunnelOrchestrator can create an empty BudgetState; the runtime does not wire the existing persisted ledger path, and compute_actual_usd is passed as metadata / may be estimated rather than settled owner spend. The generic owner bool is consumer_asserted. For FUN-03/B164, promotion_write_allowed is derived from degradation_mode==normal and rechecked as the same bool; it is not an independently issued/current permission. Existing native guard-removal evidence is bounded and does not establish arbitrary callback authority.

**Выбранная реализация.** Wire the actual resource owner measurement through the existing BudgetMiddleware, BudgetState and BudgetLedger/FileBudgetLedger path; do not create a second budget subsystem. Preserve reserve/settlement semantics and persisted snapshot readback. Bind charge to stable run/candidate/attempt identity; if retries are possible, extend this ledger with an atomic idempotent charge-event identity or specify a bounded at-most-once writer contract. Keep stage and aggregate verdicts distinct. For B164, require an owner-issued typed permission bound to candidate, run/ticket generation, promotion-write purpose, policy/schema version, issuer/verifier provenance, validity interval and revocation epoch; the effect owner independently verifies it and rechecks current revocation/generation immediately before commit. This permission is a proposed integration contract; no current API is claimed.

**Отвергнутый вариант.** Do not infer charge/publication from a callback True, displayed cost, empty regressions array, fixture-only successful comparison, or DTO field presence.

**Canonical paths.** policy-engine/src/polisyos/scientist/methods/search/funnel/; policy-engine/tests/unit/scientist/search/funnel/; policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/funnel-01-continuation.json@origin/codex/e02-D-funnel; policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/funnel-02-config-outcomes.json@origin/codex/e02-D-funnel; policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/funnel-03-calibration-promotion.json@origin/codex/e02-D-funnel; policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/funnel-final-production-invocation.log@origin/codex/e02-D-funnel; policy-engine/src/polisyos/scientist/orchestration/engine/budget.py@1a2fbb73; policy-engine/src/polisyos/scientist/orchestration/engine/budget_ledger.py@4a223413; policy-engine/src/polisyos/scientist/orchestration/engine/budget_middleware.py@9ec1ef86; policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py@e0656b09; policy-engine/src/polisyos/scientist/orchestration/run_policy_blueprint_runtime.py@0b6832cd; policy-engine/src/polisyos/scientist/orchestration/level6_promotion.py@b77bfbf3

**Зависимости.** D-W02: FUN-01/02/03; resource owner A for real debit; actual production invocation/candidate identity

**Положительная функция и независимый oracle.** The native guard-removal control changes effect 0→1 and proves that specific functional guard. Existing funnel suite receipts prove bounded fixtures only. They do not prove persisted budget settlement or typed owner permission. New positive acceptance must invoke the real measured resource owner and real test writer, read the persisted FileBudgetLedger snapshot before/after, verify exact settled spend, reservation cleared and one stable charge identity; valid owner-verified permit must allow the bound write.

**Negative control и приёмка.** Remove the ledger settlement call while preserving displayed stage cost=1; persisted spent/reserved readback must show no charge and the gate must fail. Retry the same charge event and prove it is not double-counted; compare full/split runs by ledger snapshots for the same events, not by displayed costs. Remove the native guard with markers preserved and confirm its existing effect probe goes red. For B164 retain promotion_write_allowed=true while supplying absent, fake, wrong-issuer/candidate/run/ticket/purpose, expired or preflight-then-revoked permission; effect count must remain zero. Recheck current permission at commit. Classify this as the same B164 owner-permission class one level deeper (P40), not a new bool-hardening class; until owner verifier is wired the capability remains bridge_missing. Proposed only; no receipt.

**Границы.** Integer fixture 1..120, BCa seed 17, medium 24/50 vs full 120/120 does not prove statistical/publication validity. Candidate code does not establish production runtime invocation, measured resource owner, persisted actual charge, idempotency semantics or typed permission/revocation; those remain not_established. Existing local fixture evidence is bounded.

**Runtime.** Observed CPython 3.14.2 and later bounded oracle at CPython 3.14.7; actual production deployment not established.

**Основания.** policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/funnel-final-suite.log@origin/codex/e02-D-funnel; policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/funnel-native-owner-removal-probe.log@origin/codex/e02-D-funnel; policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/funnel-production-invocation-summary.json@origin/codex/e02-D-funnel

<a id="methods-e"></a>

## E — выбранные методы

<a id="e-m1"></a>

### E-M1 — Calibration objective, Hessian, and covariance meaning

**Finding IDs.** B179; B180; B181; B182; B195; B196; B203

**Свойство.** The derivative belongs to the exact declared objective; an inverse Hessian is inferential covariance only for an explicitly supported likelihood or posterior approximation, at an admissible optimum with sufficient curvature and numerical precision.

**Сегодняшнее расхождение.** G97 loss.py computes squared/Huber loss, not a likelihood. hessian.py returns inverse eigenvalue-clipped curvature as covariance/std; a negative, singular, or near-flat direction can become finite after clipping. It records infinite condition number but still emits covariance. JAX float32 is the tested default profile. The final candidate also needs objective-consistent scoring; a cache hit requires full objective identity.

**Выбранная реализация.** Reuse JAX grad/hessian for JAX-compatible smooth functions and NumPy eigvalsh/eigh for a small explicit spectrum guard. Own only the typed admissibility/result gate, objective-kind lineage, finite-difference cause, rank/condition disclosure, and exact cache key. Keep finite differences as a comparison/fallback diagnostic with a convergence check, not a statistical fallback.

**Отвергнутый вариант.** Do not replace the loss with SciPy optimize or add an inference package merely to give a generic loss a covariance. Do not regard damping/eigenvalue clipping or float64 post-casting as proof of valid covariance.

**Canonical paths.** policy-engine/src/polisyos/foundry/calibration/loss.py@6bc8e542a8ed4a3cf9f85b218397ee0d7e601dde; policy-engine/src/polisyos/foundry/calibration/hessian.py@1543998995fcbdf4f30bfa1c1c36cb54ee8324e7; policy-engine/src/polisyos/foundry/calibration/calibrator.py@f64ce5319b4fd88c98ba6cd5bab7af9e8f880c37; policy-engine/tests/unit/foundry/calibration/test_hessian.py@7cdc95c7e9086deb544850ea007fc65fd399e4e6; policy-engine/tests/unit/foundry/calibration/test_measurement.py; policy-engine/tests/unit/foundry/calibration/test_pure_executor_semantics.py; policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAL-02.md@c40d4acae1ce58b597267255026d9356565828fd#B179-B182; policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAL-03.md@c40d4acae1ce58b597267255026d9356565828fd#B195; policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAL-04.md@c40d4acae1ce58b597267255026d9356565828fd#B196,B203

**Зависимости.** JAX 0.8.2 CPU, NumPy 2.3.5, Python 3.14.2 were present in cited E receipts. JAX x64 is disabled by default; explicitly record dtype/backend rather than toggling a process-global setting inside a library.

**Положительная функция и аналитический oracle.** **dgp**: Declared Gaussian likelihood with negative log likelihood L(theta)=0.5*((theta1-1)^2/4+(theta2-2)^2/9).; **expected**: MLE=(1,2), Hessian=diag(1/4,1/9), inverse observed information=diag(4,9), standard errors=(2,3). Compare autodiff, independent analytic derivative, and two finite-difference steps.

**Различающий negative.** **cases**: Same Huber objective without a probability model: permit curvature diagnostic, refuse inferential CI/covariance.; Saddle L(theta)=theta1^2-theta2^2: raw negative curvature cannot be clipped and called a valid uncertainty law.; Constant objective/rank zero: return non-identifiable/unavailable, not a finite precision estimate.; Change only weights, seed, objective identity, dtype, or candidate theta while keeping a parameter vector: Hessian cache must miss.; **removal_probe**: Remove the raw-spectrum/admissibility gate while leaving result fields and finite covariance construction; the saddle and flat cases must become visibly failing.

**Ошибка и покрытие.** Inverse observed information is a large-sample MLE covariance only with an explicit likelihood, interior regular identifiable optimum, and stated sampling assumptions. A full negative-log-posterior Hessian supports only local Laplace approximation. For generic loss, dependent/misspecified rows, or repaired non-PD Hessian, report curvature-only or unavailable; use owner-selected sandwich/block method only after its estimand is fixed.

**Runtime.** No new package required. Float32 derivative fidelity is not equivalent to float64 because casting after the JAX calculation cannot recover lost precision.

**Следующая проверка.** Targeted calibration tests plus the analytic DGP; assert exact objective identity, raw eigenvalues/rank, no interval for bad/unsupported curvature, last returned optimizer candidate was scored with identical data/weights/seed, and removal probe fails. These tests were not run by this research agent.

**Основания.** policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/pcl.json@3b4814cb0033d2e3bb08590d6e62207a501fba17; policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/cal05-mapped-schedules.json@82d7ba5fa0626ebbecf415821195d8f3870bc1ff; [первичный источник](https://docs.jax.dev/en/latest/_autosummary/jax.hessian.html); [первичный источник](https://docs.jax.dev/en/latest/101/default_dtypes.html); [первичный источник](https://link.springer.com/article/10.1007/s00211-021-01266-9)

<a id="e-m2"></a>

### E-M2 — Joint input law, covariance, and empirical carriers

**Finding IDs.** B186; B187; B188; B192; B197; B198; B199; B200; B201; B202

**Свойство.** Propagation must preserve the actual vector law and named estimands. Marginals or a producer-supplied ID do not prove independence or authenticated row pairing. Mean, median, and central quantile interval are distinct functionals.

**Сегодняшнее расхождение.** G97 empirical carriers are aligned by axis, length, weights, and declared joint_sample_id, but that id is non-authoritative. More importantly, missing dependency metadata passes: has_unknown_dependency catches explicit unknown labels only; no-carrier _build_empirical_joint_spec returns no failure and MC assigns separate random keys, implicitly multiplying marginals. Delta can also use diagonal covariance when no cross-covariance is given. Standard covariance mode clips small/zero eigenvalues to jitter; preserve_singular is opt-in.

**Выбранная реализация.** Reuse strict typed carrier schemas and NumPy eigendecomposition. Own a generic admission rule requiring a verified independence/product-law declaration or a source-bound full joint carrier; absent/partial law becomes unknown and non-gating. Keep singular covariance when perfect ties are declared. Make point and interval functionals an explicit typed pair before broadening UncertaintyEnvelope.

**Отвергнутый вариант.** Do not infer independence from absent correlation, shared list length, or string id. Do not make a singular law full-rank with invisible jitter. Do not force posterior mean into a central quantile interval by widening the interval or relabeling mean as median.

**Canonical paths.** policy-engine/src/polisyos/foundry/uncertainty/covariance.py@f0100d090a44305f141dbbf3a4204c00a408d143; policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py@7bd39d2e9e437a4b98a292a8da7b3744f7f3182c; policy-engine/src/polisyos/foundry/uncertainty/delta.py@043fed441a7a9a2101b0d90b9472c589e72a32c7; policy-engine/src/polisyos/ir/analytics/uncertainty.py@0a2495855d707a6548da6983bdef9abed9c4b0c7; policy-engine/tests/unit/foundry/uncertainty/test_covariance.py@cb3c775ed58a836adf4048d20c24176267b29795; policy-engine/tests/unit/foundry/uncertainty/test_monte_carlo_b194.py@1a750bdf9c493940c1476ff3522a706f55e40920; policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAL-06.md@c40d4acae1ce58b597267255026d9356565828fd#B197-B198; policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/UQP-02.md@c40d4acae1ce58b597267255026d9356565828fd#B187-B188; policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/UQS-01.md@c40d4acae1ce58b597267255026d9356565828fd#B199-B202

**Зависимости.** JAX/NumPy paths are present. Current MC marginal samplers use NumPy/SciPy transforms; SciPy belongs to analytics/sensitivity extras and is not guaranteed in every runtime profile.

**Положительная функция и аналитический oracle.** **dgp**: One scalar g~Normal(0,0.05^2) generates the joint vector (a,b)=(g,g); define y(a,b)=a-b.; **expected**: The input map Jacobian is J_(a,b)<-g=[1,1]^T, so Sigma_ab=J Var(g) J^T=0.0025*[[1,1],[1,1]] has rank 1. The output gradient is grad_(a,b)y=[1,-1], hence Var(y)=grad^T Sigma_ab grad=0. For two truly independent inputs with the same 0.05 standard deviations, Var(a-b)=0.005.

**Различающий negative.** **cases**: Remove all dependence declaration but leave both marginals unchanged: result must be unknown/non-gating, not independently sampled.; Use two empirical vectors with same declared ID/axis/length but different source row lineage: provenance admission must reject them.; For 99 posterior values 0 and one value 100, mean=1 while central 5-95% quantiles are [0,0]; preserve both meanings without claiming containment.; **removal_probe**: Remove source-law admission while retaining the input fields and numeric output markers; the absent-law case must no longer produce an eligible propagation result.

**Ошибка и покрытие.** A full covariance determines a joint Gaussian only under a declared Gaussian law; it is not a general non-Gaussian dependence model. Delta is local. Empirical rows preserve only the represented finite law. B197 requires the actual configured calibration producer, verified persisted report and welfare consumer; it is not blocked by the B201/B202 wire-semantic ratification. B201/B202 require that narrowly scoped semantic decision. Carrier/shape validation alone cannot close any of these criteria.

**Runtime.** No new numerical package. Float64 NumPy PSD validation followed by float32 JAX conversion still loses precision/rank distinctions on output; record dtype and tolerance.

**Следующая проверка.** Run covariance and Monte Carlo tests plus serialization/readback at the actual consumer; tied-variable oracle must stay rank-1, absent-law removal probe must fail closed, corrupt row/column alignment and materially indefinite matrix must reject. Separate any change to mean/interval contract behind a semantic owner decision.

**Основания.** policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/bootstrap-statistic-identity.json@47235add0ff898bcaa027382661ea3f1de5b051d; [первичный источник](https://docs.jax.dev/en/latest/101/default_dtypes.html)

<a id="e-m3"></a>

### E-M3 — MC propagation with per-draw failures

**Finding IDs.** B186; B189; B190; B191; B194

**Свойство.** The estimand is over the declared input law and complete requested draw denominator; a mean over executions that succeeded is conditional on execution unless the failure region has a defined output or is excluded by an explicit domain contract.

**Сегодняшнее расхождение.** G97 now records sample input hashes, per-output failure codes, requested/attempted/success/unattempted counts, and marks incomplete output candidate-only/non-gating. This is a bounded mechanism improvement, not an unconditional estimator or served consumer. Default independent sampling also remains dependent on the joint-law declaration decision above.

**Выбранная реализация.** Own only draw lifecycle, same-input transient retry trace, typed failure provenance, denominator, and conditional-vs-unavailable scope. Reuse the native MC engine after law admission. Retry a draw only when failure is independently classified transient; preserve original attempt identity.

**Отвергнутый вариант.** Do not drop errors and compute a nominal CI over successful rows, impute zero, or repeat structurally unsupported input values until they pass.

**Canonical paths.** policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py@7bd39d2e9e437a4b98a292a8da7b3744f7f3182c; policy-engine/tests/unit/foundry/uncertainty/test_monte_carlo_b194.py@1a750bdf9c493940c1476ff3522a706f55e40920; policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_uncertainty.py; policy-engine/src/polisyos/scientist/orchestration/workflows/policy_design.py

**Зависимости.** JAX PRNG and NumPy buffers; exact supported numerical profile in E handoff. Actual admitted production law and served evaluator evidence are not in compact receipts.

**Положительная функция и аналитический oracle.** **dgp**: Bounded deterministic Y=f(X) for all X in a declared support, e.g. X~Uniform(0,1), Y=X.; **expected**: All requested draws have one terminal outcome; sample mean tends to 0.5, empirical output distribution is Uniform[0,1], and denominator identity survives persisted readback.

**Различающий negative.** **dgp**: X~Uniform[-1,1], but evaluator is undefined for X<0.; **expected**: Successful-only mean 0.5 is conditional on X>=0; the unconditional push-forward is unavailable unless the domain law or failure output is specified. Must not emit unconditional 95% CI.

**Ошибка и покрытие.** When a draw fails, current output correctly downgrades to heuristic/candidate-only locally. The source receipt does not establish downstream consumer refusal, authenticated input law, or production completeness; B194 is not finding-closed.

**Следующая проверка.** Extend test_monte_carlo_b194.py through the actual consumer and persisted artifact readback. Assert complete denominator/outcome codes, same-input transient retry only, domain failure remains non-gating, source-law unknown remains unknown, and removal of outcome completeness is caught.

**Основания.** policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/bias-statistical-support.json@c6c3d6bcfc65c57d89810a728254d3a891a2c7c2; policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/bias-statistical-support.checks.json@97c85fae2d4505ec8248540d98b9556296244208

<a id="e-m4"></a>

### E-M4 — Adaptive MC target and RQMC error

**Finding IDs.** B193; B188

**Свойство.** Stopping requires a declared numerical estimand and an error bound valid for the actual sampling/stopping schedule. Predictive spread is different from numerical integration error.

**Сегодняшнее расхождение.** Adaptive code compares central output percentile width divided by absolute sample mean against a threshold; that width does not shrink as N grows. RQMC code splits arbitrary total counts into replicas/chunks, can discard the incomplete Sobol tail, and labels a run RQMC_REPLICATES based on replica count without calculating replication variation. The broad provenance scope includes expectation, quantile, interval, and CDF although one certificate does not establish all four.

**Выбранная реализация.** Smallest defensible near-term route: independent fixed-size pilot for variance planning, freeze the main sample count before the estimation run, and compute one fixed-N interval; pilot data are not pooled into that estimator. If true optional stopping is required, implement/test a theorem-backed time-uniform confidence sequence for the declared IID/bounded target. For RQMC use SciPy Sobol power-of-two draws per independent scramble and estimate error from replicate estimator values, not pooled output spread.

**Отвергнутый вариант.** Do not repeatedly peek at fixed-N intervals, stop on quantile spread/mean, or call arbitrary partial Sobol prefixes balanced. Do not call two scrambles a certificate without an estimator-specific error calculation.

**Canonical paths.** policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py@7bd39d2e9e437a4b98a292a8da7b3744f7f3182c; policy-engine/src/polisyos/foundry/uncertainty/config.py; policy-engine/src/polisyos/foundry/uncertainty/quasi_mc.py@680e09229942fb2e4f71cf3bd7b066ba9b0cd839; policy-engine/src/polisyos/ir/analytics/uncertainty.py@0a2495855d707a6548da6983bdef9abed9c4b0c7; policy-engine/tests/unit/foundry/uncertainty/test_adaptive_stopping.py@e5a68c9ee57cd2f6956cae2779aba13e93ed0d19; policy-engine/tests/unit/foundry/uncertainty/test_quasi_mc.py@3843bd2704aa5ba18776df8f3f6b9a4bf3ad4f8d

**Зависимости.** SciPy QMC available through sensitivity/analytics profile; absent backend is UNRUN, not PASS. The currently checked Python 3.14.2 environment used SciPy 1.16.3 and CPU only.

**Положительная функция и аналитический oracle.** **dgp**: Let IID Xi~Bernoulli(0.001), estimate mu=E[X]=0.001 with absolute error epsilon=0.05 and familywise confidence 95%. Use an independent pilot m=256 and split delta_pilot=delta_main=0.025. For pilot mean xbar and second moment qbar=mean(X_i^2), Hoeffding plus a union bound gives a=sqrt(log(4/delta_pilot)/(2m)); with probability >=1-delta_pilot, mu>=max(0,xbar-a) and E[X^2]<=qbar+a. Thus U=min(1/4,max(0,qbar+a-max(0,xbar-a)^2)) is an upper bound on variance. Freeze N=ceil((2U+2epsilon/3)*log(2/delta_main)/epsilon^2) before the independent main run, from the bounded Bernstein inequality. Exclude pilot draws from the reported mean. If the pilot observes zero successes, U=a=0.0995613 and N=408; pilot+main cost is 664 draws, versus 738 for a fixed Hoeffding budget at the same epsilon/alpha. The coverage guarantee is conditional on the declared IID [0,1] law; pilot-bound failure plus main-run failure is at most 0.05.; **expected**: The main estimate targets mu=0.001, reports its fixed-N uncertainty separately from predictive spread, and has an absolute-error guarantee <=0.05 with at least 95% coverage under the stated law. N is selected only from the independent pilot and frozen before main draws; do not pool pilot into the reported estimate. This is a genuine pilot-to-frozen-budget discriminator, not repeated-peek optional stopping.

**Различающий negative.** **cases**: Y~Normal(0,1): predictive 95% span is about 3.92 at both N=200 and N=10000, while MCSE scales as 1/sqrt(N). Current percentile-spread rule cannot test estimator precision.; Use several seeds whose first fixed-N interval misses, then keep sampling until one passes: repeated fixed-N coverage is no longer a valid nominal sequential guarantee.; Set total Sobol N=1000 and 4 replicas: each actual replicate must be a full 2^m net or must not carry the full balance/RQMC error status.; **removal_probe**: For the selected pilot-to-frozen-Bernstein route, remove the pilot variance upper bound, frozen-N rule, or independent-main-run admission while retaining certificate/status markers; the analytic pilot-N/coverage oracle must fail. For RQMC, remove the observed replicate-estimator variance/error calculation while retaining RQMC markers; the estimator-specific error oracle must fail.

**Ошибка и покрытие.** Pilot validity requires independent IID samples from the same bounded law for pilot and main run. Pilot error budget delta_pilot bounds the variance upper-bound failure; conditional on a valid upper bound and independent main stream, fixed-N Bernstein failure is <=delta_main, giving total failure <=delta_pilot+delta_main. Dependence, unbounded outputs, changing simulator law, outcome-dependent failures, or pooling the pilot need a different proof or a declared limitation. This frozen-budget plan does not justify optional peeking; a requested anytime stop requires a theorem-backed confidence sequence valid under the admitted sampling assumptions.

**Следующая проверка.** Add an analytic Bernoulli test with a deterministic all-zero pilot branch: derive U and N exactly (408 for m=256, alpha split .025/.025, epsilon .05), then assert the independent main run preserves the fixed-N bound and excludes pilot rows. Across independent generated streams verify coverage against the declared law. Negative controls: change law after pilot, pool pilot, or repeatedly peek at fixed-N intervals; each must invalidate the guarantee. QMC tests must separately verify full power-of-two rows per scramble and estimator-specific replicate error.

**Основания.** [первичный источник](https://doi.org/10.1214/20-AOS1991); [первичный источник](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.Sobol.html); policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/cal05-mapped-schedules.json@82d7ba5fa0626ebbecf415821195d8f3870bc1ff; [первичный источник](https://doi.org/10.1080/01621459.1963.10500830)

<a id="e-m5"></a>

### E-M5 — Morris screening and Sobol variance decomposition

**Finding IDs.** B97; B98; B99; B100; B101; B102; B103; B104; B105

**Свойство.** Producer and analyzer consume one matching design and distribution; Morris effects are based on valid single-coordinate trajectories with declared scale; Sobol ANOVA indices are for a declared independent-input law.

**Сегодняшнее расхождение.** SALib 1.5.2 Morris geometry guard is locally well evidenced (98 native tests and removal control), but it validates geometry, not input provenance or selection bias from dropped failed draws. Effect scale differs between unit-space SALib point effects and physical-scale uncertainty helper. Sobol must not be used on correlated marginals as if independent. Separate Foundry regression_first_order_proxy is not Sobol.

**Выбранная реализация.** Reuse SALib native Morris/Sobol sampler+analyzer. Own a generic design contract validating full trajectory geometry, parameter/distribution identity, row order, local RNG seed, budgets, denominator, scale/unit, and output failure handling. Use a separately owner-approved dependent-input measure where the law is dependent.

**Отвергнутый вариант.** Do not rewrite standard Morris/Sobol estimators, mix arbitrary rows with SALib analyzer, silently change the design distribution, or treat finite/divisible matrices as valid Morris trajectories.

**Canonical paths.** policy-engine/src/polisyos/scientist/methods/doe/analysis.py@c0c3616a8e77702963b85d5450a91437e0fe225e; policy-engine/src/polisyos/scientist/methods/doe/morris_geometry.py@8e75b7d9fdccaba0c564bb49874056dd20a8bba0; policy-engine/src/polisyos/scientist/methods/doe/uncertainty.py@541e2e5912916351935ee504311b8e3bbdaea019; policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py@7bd39d2e9e437a4b98a292a8da7b3744f7f3182c; policy-engine/tests/unit/scientist/methods/doe/test_morris_geometry.py@a6ca39489c3cd8043893047e6f20e33aea638a91; policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/doe-morris-geometry.json@ff2d10e22f6ac443ffc7701fbb8022d16a8bafe4

**Зависимости.** SALib 1.5.2, SciPy 1.16.3, NumPy 2.3.5, Python 3.14.2 were actually tested in isolated DOE environment; pyproject declares SALib and SciPy only in sensitivity extra.

**Положительная функция и аналитический oracle.** **morris**: y=2x+3z; x in [0,10], z in [0,1]. Physical derivatives are 2 and 3; unit-coordinate full-range effects are 20 and 3. Exact expected result depends on declared unit field and must be stable under trajectory permutation.; **sobol**: Independent X1,X2~Uniform(0,1), Y=aX1+bX2: S1=a^2/(a^2+b^2), S2=b^2/(a^2+b^2), ST=S, second-order terms 0.

**Различающий negative.** **cases**: A Morris row changes two coordinates, has a tiny off-grid step, or mixes wrong delta: refuse point/UQ/PCA output.; Drop a failed input-dependent row: retain original denominator and mark selection bias/unavailable instead of analyzing only survivors.; Set X2=X1 with unchanged marginals: ordinary independent-input Sobol result is not admissible.; Sampler uses triangular/normal transform while analyzer interprets uniform bounds: reject mismatch.; Set n just above budget or use global RNG: respect budget and preserve isolated seeded stream.; **removal_probe**: DOE receipt removed the geometry validator in an isolated process and the two-coordinate adversarial Morris test failed, which establishes that exact guard's behavior, not provenance/selection closure.

**Ошибка и покрытие.** Morris mu-star/sigma are exploratory screening summaries over sampled trajectories, not causal effects. Sobol indices are variance contributions under the matching independent law. Their estimator confidence/bootstrap output is separate from design validity and requires correct resampling/seed/replicate semantics.

**Следующая проверка.** Existing test_morris_geometry.py and remediation DOE-01/02/03 plus native SALib. Add closed-form linear Morris/Sobol fixtures; test independent and correlated DGPs; test exact sampler/analyzer pairing, failure denominator, resource limit, seed isolation, nonuniform units, and persisted design/result readback. Existing geometry receipt is bounded for B102 only.

**Основания.** [первичный источник](https://doi.org/10.1080/00401706.1991.10484804); [первичный источник](https://doi.org/10.1016/S0378-4754(00)00270-6); [первичный источник](https://salib.readthedocs.io/en/latest/user_guide/basics_with_interface.html); policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/doe-morris-geometry-checks.txt@97c85fae2d4505ec8248540d98b9556296244208

<a id="e-m6"></a>

### E-M6 — Forecast calibration, backtest aggregation, and curve evidence

**Finding IDs.** B32; B166; B167; B168; B169; B170; B171; B172; B173; B174; B175; LA-051; LA-052; LA-053

**Свойство.** Evaluate an issued forecast against later outcomes for the same estimand, issue/horizon/vintage, source law and method rule. Separate empirical coverage, CI/credible interval, predictive interval, calibration curve, and parameter fit. Make missingness, scenario weights, temporal dependence and estimator identity explicit.

**Сегодняшнее расхождение.** FRC producer binds method/context but is implemented_but_not_orchestrated; A owns generation_cycle.py. Some prior mapping substituted nominal interval level as observed coverage/pass rate. PCL curve gate fixed incomplete/NaN rows but does not recreate history or complete forecast lineage. Backtest code has source findings on denominators, split identity, RMSE macro-vs-micro, residual independence, CV statistic and temporal folds.

**Выбранная реализация.** Reuse SciPy fixed-N tests/bootstrap only where assumptions and resampling unit match; use proper interval/quantile scores with actual outcomes; own forecast identity/time/denominator binding and explicit micro/macro aggregate. For dependent time data use declared rolling/blocked splits and block/cluster method, not IID resampling.

**Отвергнутый вариант.** Do not infer observed hit rate from nominal confidence level, use causal-parameter CI as outcome prediction interval, convert missing outcomes to passes/misses without policy, collapse scenario splits silently, or treat p>alpha as proof of no meaningful bias.

**Canonical paths.** policy-engine/src/polisyos/scientist/methods/backtesting/forecast_owner.py@e9302eb353ab7be6b03f4812ab9b473fb9555f64; policy-engine/src/polisyos/scientist/methods/backtesting/; policy-engine/src/polisyos/ddm/calibration/; policy-engine/tests/unit/remediation/test_frc_01.py; policy-engine/tests/unit/remediation/test_frc_02_owner.py; policy-engine/tests/unit/scientist/methods/backtesting/; policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/frc.json@6d80765d9a336f3c7840348234039a9a293fc4e7; policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/pcl.json@3b4814cb0033d2e3bb08590d6e62207a501fba17; policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/BKT-02.md@c40d4acae1ce58b597267255026d9356565828fd#B171; policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/BKT-03.md@c40d4acae1ce58b597267255026d9356565828fd#B172-B173; policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/BKT-04.md@c40d4acae1ce58b597267255026d9356565828fd#B174-B175

**Зависимости.** FRC numerical receipt used NumPy evaluator fixtures, not forecast estimator backend. SciPy 1.16.3 is present in E analytic/test profile; statsmodels was not installed in PCL receipt. Full production forecast history/outcome inputs are not available in this compact source review.

**Положительная функция и аналитический oracle.** **dgp**: Issue 100 nominal-90% predictive intervals then supply 100 observed outcomes all outside the interval; use a second held-out set with exactly 90/100 hits and matching origin/horizon.; **expected**: First set coverage=0/100 and fails any nominal-90% coverage criterion; second empirical coverage=0.9 subject to uncertainty bound, with interval-width/proper-score reported separately. Change only outcome rows and measured result changes.; **bkt03_residual_mean**: **dgp**: For the BKT-03 two-sided one-sample Student t test of residual mean against zero, compare balanced errors [-0.01, 0, 0.01] with the separate small-n unequal-error vector [0.5, 1.5, 2.5].; **expected**: For balanced errors, mean=0, sample SD=0.01, t=0, df=2, p=1. For [0.5, 1.5, 2.5], mean=1.5, sample SD=1, SE=1/sqrt(3), t=2.59807621135, df=2, p=0.1216899343. The first case is balanced, not significant evidence of zero population bias; if SciPy is unavailable, nonzero residuals retain descriptive values but statistical support is unavailable/degraded and cannot earn trust grade.

**Различающий negative.** **cases**: No outcome rows, or wrong horizon/vintage: coverage unavailable, not nominal level and not zero-miss pass.; A/B171 residuals [0,10,10] as one scenario have micro RMSE about 8.165; split into [0] and [10,10] yields macro 5. These are different named estimands, not interchangeable due to sharding.; Mean-zero but nonzero residuals with unavailable test backend cannot earn Grade A.; Unknown bootstrap statistic typo rejects before sampling; temporal rows do not silently use IID bootstrap.; Training/calibration, forecast issue, prediction horizon and observation timestamps remain separate.; **removal_probe**: Keep nominal-level/method markers but remove observed outcome binding; the coverage gate must fail.

**Ошибка и покрытие.** Proper quantile/interval scores reward both sharpness and misses. Empirical coverage uncertainty requires IID forecast cases or a declared clustered/time-block method. A curve ECE is not universal forecast calibration evidence. FRC method binding has no completed generation-cycle bridge or complete source lineage in current handoff.

**Следующая проверка.** At the A-owned generation_cycle boundary, persist and reopen exact forecast/method/context/outcome references; evaluate actual held-out outcomes; corrupt/remove outcome ref and temporal identity to ensure consumer refuses. Existing targeted test paths: tests/unit/remediation/test_frc_01.py, test_frc_02_owner.py; tests/unit/scientist/methods/backtesting/test_{backtesting,calibration_curve,temporal,bootstrap,distributional,cv}.py. Distinguish fixed-N and correlated evaluation paths.

**Основания.** [первичный источник](https://doi.org/10.1198/016214506000001437); [первичный источник](https://www.annualreviews.org/content/journals/10.1146/annurev-statistics-032921-020240); [первичный источник](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html); policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/frc-logs/numerical-witness.json@97c85fae2d4505ec8248540d98b9556296244208

<a id="e-m7"></a>

### E-M7 — DDM expiry and calibration-status consumption

**Finding IDs.** LA-054; LA-055; LA-056

**Свойство.** A downstream readiness/promotion decision consumes the same admitted calibration report, subject identity, rule, time roles, expiry/invalidation trigger, evidence completeness and owner-authorized status policy.

**Сегодняшнее расхождение.** A checker already exists, but audit/monitor/registry paths drop source validity/identity or can reconcile status inconsistently. This is an evidence bridge and status/time semantic issue, not a new estimator.

**Выбранная реализация.** Reuse check_calibration_validity and propagate immutable report/model/metric/rule identities, valid_until, source times and invalidation refs across audit, monitor event, registry and public surface. Own only the bridge and one explicitly authorized promotion policy.

**Отвергнутый вариант.** Do not duplicate expiry formula, substitute horizon TTL for validity, infer missing evidence as a clean signal, or unify explicit R2 signoff into an implicit auto-pass.

**Canonical paths.** policy-engine/src/polisyos/ddm/calibration/audit.py; policy-engine/src/polisyos/ddm/integration/monitor.py; policy-engine/src/polisyos/ddm/integration/model_registry.py; policy-engine/src/polisyos/ddm/integration/events.py; policy-engine/src/polisyos/ddm/readiness/readiness_mapper.py; policy-engine/tests/unit/ddm/test_readiness_mapping.py@9f4e7cc5a66c0abcd9c015bf87abc04e58158d4b; policy-engine/tests/unit/ddm/test_delayed_label_replay.py; policy-engine/tests/unit/ddm/test_full_acceptance.py

**Зависимости.** DDM semantic owner must decide whether explicit promotion_allowed=false is a hard veto or a baseline eligibility value, preserving named R2 human signoff. No new numerical package.

**Положительная функция и аналитический oracle.** **dgp**: Same admitted report identity with valid_until just after current time passes; current time one tick after valid_until or an invalidation trigger fires.; **expected**: Registry/monitor view changes from eligible to expired/invalid and carries exact source report/time, while approved signoff case follows its explicit path.

**Различающий negative.** **cases**: Swap model or metric identity while keeping status=pass: consumer must reject.; Set promotion_allowed=false in persisted record: reopening may not turn it true absent authorized signoff.; Empty/incomplete delayed-label window is unavailable, not a clean drift/no-drift result.; **removal_probe**: Drop valid_until/report identity from the bridge while keeping green status fields; readiness must fail closed.

**Ошибка и покрытие.** LA-054/055 are bridge/status integrity; LA-056 is facade/import boundary. No claim of new statistical test validity is appropriate.

**Следующая проверка.** Targeted readiness, delayed-label replay, facade, full-acceptance tests plus persist/reopen/readback; test stale, trigger-invalidated, wrong-subject, incomplete feed, false permission and explicit owner-approved signoff. These tests were not run by this research agent.

**Основания.** policy-engine/src/polisyos/ddm/calibration/calibrate.py; policy-engine/src/polisyos/ddm/calibration/audit.py; policy-engine/src/polisyos/ddm/integration/model_registry_gate.md; policy-engine/docs/research/e02-cloud-test-plan/execution-organization/finding-owners.tsv@97c85fae2d4505ec8248540d98b9556296244208#LA-054-LA-056

<a id="methods-f"></a>

## F — source-bound методы и отдельные решения о приёмке

**Текущий basis.** [F receipt registry](F.md#receipts) фиксирует carrier/source/tree/check identity. Этот раздел сопоставляет опубликованные результаты с оригинальными cards; он не запускает scientific waves, не объявляет общий composed runtime PASS и не принимает authority/G. Предшествующий G97 method plan целиком сохранён как `method-decisions.md@d9c48853c5ab9ad7473df204bf3a7a1995a32057`; его future/UNRUN утверждения относятся к тому source. Stable F-M1–F-M16 anchors сохранены.

<a id="f-m1"></a>

### F-M1 — Typed causal uncertainty: distribution, posterior и estimator CI

**IDs / свойство.** B215/B223: fixed-fit outcome/ITE draws, posterior credible intervals и sampling CI estimator — разные quantities. More draws уменьшают MC error, но не создают estimator refit/sample law.

**Current implementation/evidence.** SCM6d Gaussian abduction использует `U|x`: mean `D Aᵀ(A D Aᵀ)⁺(x-b)`, covariance `D−D Aᵀ(A D Aᵀ)⁺A D`; reconstruction/singular inconsistency и shared-U contrasts проверены. Typed query/twin/CAS readers сохраняют distribution/credible meanings и не повышают unsupported partial nonlinear posterior до gate-eligible CI. ROOT3afb связывает actual selected CAS bytes/manifest, complete inputs и current report diagnostic basis; это отдельное consumer свойство, не новая inferential calibration.

**Oracle/negative.** `U~N(0,1),Y=U+ε, ε~N(0,1),Y=2` даёт `U|Y=2~N(1,.5)`; known `Y=1+3X` даёт same-arm0 и do2−do0=6. Fixed-model percentile output с сохранёнными CI markers не становится sampling CI. Unknown/nonlinear partial evidence остаётся typed limited.

**Limits.** No real-world graph/identification/parameter-posterior authority; новый refit-bootstrap estimator CI требует собственного source/units/refit/coverage receipt и не комиссионируется этим update.

<a id="f-m2"></a>

### F-M2 — TMLE nuisance identity, diagnostics и study resources

**IDs / current evidence.** B54 original fit-cache criterion closed на TMLE55d2: explicit key остаётся namespace поверх content identity, immutable issued numeric fit cores отделены от current diagnostic reports. Real sklearn fits/folds/data axes, reader mutation и native DGP/removal controls измерены в `F/tmle-20261006.json`.

**Distinct B56 remainder.** Local fold execution/metadata не доказывают общий admitted study/process resource cap. Latest broker/study и native report-consumer continuation packets pending; не выдавать новую функцию или unreviewed receipt за accepted closure. Все folds/repeats/seeds/results должны сохраняться, resource gate не может выиграть omission.

**Method profile.** Native targeting owner сохраняется; binary/bounded outcome fluctuation и continuous identity-link профили нельзя смешивать. EIF normal inference — declared iid/regularity/positivity asymptotic profile, не universal finite coverage. zEpid отсутствующий/import-only reference не PASS.

**Negative / authority.** Same supplied key with changed X/T/Y/fold/model misses; nested prediction/report mutation не меняет cached source. Actual simultaneous study pressure должен проверять свой реальный broker, не строку cap. Admitted real data/evaluator authority отдельно от known-DGP/cache evidence.

<a id="f-m3"></a>

### F-M3 — Standard DiD: estimability, effective covariance, diagnostic truth

**IDs.** B204/B205/B206. Native interaction coefficient сохраняет 2×2 ATT; actual HC1 iid-row и unit-cluster CR0 profiles различны. No-pre design refused; too few preperiods дают `not_testable`, не `passed`; nonrejection не доказывает parallel trends.

**Evidence.** DIDcebe `published-native`/removals и DIAGNOSTICS0b producer/maintained route. ROOT3afb actual report consumers independently recompute whole diagnostic input/result basis, including typed DiagnosticTest; изменение time_treatment при той же scalar θ обязано обнаруживаться. Standard ATT3 hand oracle и actual Statsmodels diagnostic/covariance comparison — code witnesses, не identification.

**B206 dual source.** Native .8/.95/.99 critical values/invalid-level refusal в DiD **и** RDDfb checks0/5/12; нельзя приписать RDD только DiD tree. CR0/z algebra не гарантирует small-cluster coverage.

**Proxy negative.** Producer/reader digest removal, stale/coherently forged diagnostic payload, cluster-as-HC1 и fixed95 critical removal FAIL при retained status/fields. Current worker/caller checks имеют собственные SHA; broad real parallel-trends admission UNRUN.

<a id="f-m4"></a>

### F-M4 — Dedicated DiD ownership и maintained request migration

**ID.** LA-016 — две coverage bindings к одному original block. DIAGNOSTICS0b actual maintained G2 request создаёт dedicated Standard FQN; registry/dispatcher/flags/slot/CAS и historical direct-import window сохранены. Default umbrella retirement доказан actual caller, не directory name.

**Evidence/negative.** DIAGNOSTICS checks6/7/14/15/17, caller byte replays на source0b; DIDcebe maintained benchmark controls сохраняют numerics. Old adapter/default-route removal различает реальную migration. Historical benchmark diagnostic FAIL/not_testable не превращается в detected violation или parallel-trends proof.

**Limits.** Finite maintained window, not every hypothetical external frozen client. Scientific B204–209 criteria и runtime authority принимаются отдельно.

<a id="f-m5"></a>

### F-M5 — Fixed θ_sel, share influence и closed unit-Mammen inversion

**IDs.** B207/B208/B209. Historical G97 θ_W/percentile limitations не описание DIDcebe.

**Current quantity.** Freeze eligible horizon `E_g`, `K_g=|E_g|`; `τ_g=K_g⁻¹Σ_{t∈E_g}ATT(g,t)`; `π_g=P(G=g|ever-treated)`; `θ_sel=Σ_g π_g τ_g`. IF includes cell/cohort mean contribution **and** ratio-share term `1{ever-treated}/p_E·(τ_G−θ_sel)`. Не заменять estimated shares фиксированными weights или исключать cells с draw-specific renormalization.

**Multiplier/test/CI.** One iid mean0/variance1 Mammen multiplier на panel unit shared across every cell: values `(1−√5)/2,(1+√5)/2`, probabilities `(√5+1)/(2√5),(√5−1)/(2√5)`. Center studentized draws; compare H0 against the centered law. For B draws/declared decimal confidence L, actual implementation sets `m=ceil((1−L)(B+1)−1)` and refuses insufficient m; sorted absolute-statistic index `B−m` selects the radius. Tail count uses the **same closed effect-scale intervals** as reported CI; canonical `null_rejected = tail_count < m`, with descriptive p `(1+tail_count)/(B+1)`. Decimal→integer decision and closed endpoint/nextafter controls avoid a binary .05 mismatch; a naive quantile-only inversion is not the implemented boundary.

**Actual oracle/evidence.** DIDcebe check3 complete `test_did_selected_participation.py::test_seeded_serial_panel_null_coverage_and_alternative_binomial_bounds`: **160** known serial-panel datasets per arm; true0CI154/160, true1.5CI154/160, null6/160reject, alternative160/160reject under declared binomial bounds. Hand cohort-time oracle differs from θ_W; share/uncentered/eligibility removals FAIL. DIAGNOSTICS0b changes diagnostic ownership and callers; it does **not** rerun or relabel this160-DGP wave.

**Limits.** Original finite iid/large-independent-unit scientific discriminator established; current continuation remains limited for admitted production assumptions/authority. No official external `did` witness, small-G/simultaneous bands or real-panel coverage. Fixed support failure refuses the whole requested target rather than silently changing it.

<a id="f-m6"></a>

### F-M6 — Native clean-room sharp CCT RBC; external oracle scope

**IDs.** B210/B211; B206 additionally binds requested levels. Current scientific source `fb022aa12599ee1617f83d154cd9a8027b2a58b8`, tree `bee112b9284e11b78c96d2f91660f330d68b26c7`; carrier `15a04c4400497374416e167a5f61ebc12f61b8e4`.

**Selected product implementation.** Canonical `RegressionDiscontinuity` computes published CCT2014 corrected weights `a−L d`; HC0 q-fit residual variance includes bias-estimate variance **and covariance**. Product code imports no rdrobust. Supports sharp assignment, fixed symmetric h/b, p1/2, q=p+1, triangular/uniform/epanechnikov, HC0, distinct X, full-rank weighted designs. Report binds tau_bc, se.rb, requested robustCI/options/row hash; conventional weighted/homoskedastic profile stays distinct. Small Gram matrices/vector weights avoid NxN diagonal matrices.

**Real independent reference.** Approved development-only locked rdrobust2.1.0, source `4322d4f57ce653668043f9bb262f00bbc2423554`, wheel SHA `8179f8f75445876297317a9805b81cbbf2e1e39bf804a460a8c23d0d7fa33263`, actually installed/run under isolated Python3.14.2; native application Python3.14.7. This is not metadata-only compatibility and not a product extra. GPL bundling decision is separate **only if product distribution of that external package is proposed**; it does not block the already implemented native clean-room RBC.

**Evidence / negative.** RDD checks0/1/2/3/4/5/12: actual4036 differential cases, maximum CI difference3.658229275060876e−11; 2000 independent datasets each true0/true3, coverage1879/2000 and1877/2000, declared99% binomial intervals include .95. Actual RBC removal retains markers but12108 numeric differences and84.35%/83.80% coverage reject it. Native .8/.95/.99/invalid levels and canonical dispatcher→report→CAS→fresh dematerializer are measured; no fabricated .90 test. Earlier no-MC removal harness gap remains historical; corrected final removal has the full denominator.

**Limits.** B210/B211 original finite criteria closed. No fuzzy treatment/compliance input, cluster/otherVCE/automaticselector/masspoint adjustment or real cutoff continuity/manipulation authority. Existing IK-like bandwidth and count-ratio diagnostic stay heuristic, not IK/McCrary. Full docs/architecture/compatibility failures retain their exact outcomes; original source equations and method profile are in `docs/reference/foundry/causal-rdd-profile.md@fb022aa…`.

<a id="f-m7"></a>

### F-M7 — Genuine DoWhy0.14 worker with nonauthoritative parent binding

**IDs.** B212 point-only/no manufactured CI; B213 actual estimand/contrast/target binding. The criteria are distinct and must not swap labels.

**Current evidence.** Source423 actual configured Python3.12 worker executes `CausalModel→identify_effect(proceed_when_unidentifiable=False)→estimate_effect` selected linear ATE. Python3.14 parent validates bounded versioned JSON/request/source/graph/target and persists typed report/CAS; historical installed5cd wheel/sdist consumers are real, source-specific. Missing worker/timeout/malformed version/hash/interval refuses; legitimate point-only remains no CI. ROOT3afb current typed-view/diagnostic boundary adds its own receipt; latest assembled confidence/native TMLE report continuation pending, not a new423 backend run.

**Profile/negative.** Selected control0/treatment1/ATE/no modifiers/backdoor.linear_regression; effective confidence level and one finite ordered interval exact shape(2,) or(1,2). Multirow/reversed/nonfinite/mismatched level refuses, never flatten/swap/fabricate. Real Statsmodels independent OLS interval and known confounded linear DGP; changed adjustment/target cannot pass merely on estimand type string. Mediation profiles unsupported absent actual method-specific input/oracle.

**Runtime/authority.** DoWhy0.14 excludes Python3.14; application markers remain excluded and are not positive witnesses. Explicit locked3.12 computation profile is not whole-app downgrade or parallel fake backend. Source423 finite original scientific criterion measured; current whole consumer/real identification/Runtime evaluator/appointment/fresh challenge remains limited/UNRUN separately.

<a id="f-m8"></a>

### F-M8 — Static ADMG separation/surgery and exact empty sibling scope

**IDs.** B216/B217, LA-007/LA-019. Shared STATIC518 admission rejects original unresolved endpoint pairs/compact temporal lag **before** native inference, no-op rule, surgery, builders or rewrites. Supported endpoint pairs are tail→arrow, reverse arrow←tail normalized, arrow↔arrow, lagNone/0.

**Complete finite denominator.** 8 providers,62 graph-taking entries/builders =57 static causal entries +5 raw endpoint/orientation utilities; actual source census2699Python files/179 resolved absolute-import/FQN callers.634 defining/cache checks and independent559 unique consumer cases PASS; 133PASS/3FAIL/2SKIP affected neighbors retained. Three malformed AMN/SID fixtures reproduce on exactbase provider; no P41 inherited label without full disjoint denominator. Actual Rule1/IDC/IDC*/CTF consumers +latent-DAG moralization oracle, not only importability.

**Negative/limits.** CPDAG Y—Z original real rewrite FAIL retained; shared admission removal no-opRule1 FAIL and reverse normalization removal directed-law FAIL. Finite static ADMG only, not arbitrary PAG completion/ID completeness. LA-007/019 exact empty files already absent base198; nonempty packages preserved, no new deletion. Latest supported filename/loader/docs/installed API packet pending separately, no invented all-external-user prerequisite.

<a id="f-m9"></a>

### F-M9 — Multiedges, deep immutable cache, known reverse и lag boundary

**IDs.** B219/B220/B214/B218. SCM6d actual NetworkX3.6.1 MultiDiGraph exporter/readback proves keyed directed/bidirected/temporal multiset/order. Historical missing-wheel/import-errors are tooling nonreceipts superseded only by this actual bounded witness.

**Cache property.** CACHE213/e2c stores deeply immutable JSON tuples and returns fresh plain tuple/dict rows; native75PASS/independent23PASS, nested/weakref/warm-copy controls, three retained-marker removals FAIL. Preceding mutable-row FAIL is preserved, not overridden by old6d overclaim; Kuzu row/CSV ABI values unchanged, no liveKuzu run.

**Profiles.** Known reverse default normalizes correctly; canonical DAG Scientist Node profile does not admit every known PAG/CPDAG type. Lag1/2/self-lag remain representation/export facts; STATIC518 refuses compact temporal inference. B214/B218 current limited; no invented dynamic estimator prerequisite to the original storage property, no identification from serialization.

<a id="f-m10"></a>

### F-M10 — Source-bound root law, fitted polynomial compatibility и SCM versions

**IDs.** B221/B222. SCM6d real selected DoWhy GCM worker fit→persisted source/row-bound SCM→fresh query is distinct from import-only NumPy fallback. Empirical roots retain aligned joint-row law; unknown/unprovided law stays typed limited.

**Original polynomial criterion.** POLY6f actual existing `_fit_additive_noise_poly`→explicit manualSCM1.0→realCAS/dispatcher query/twin fresh process executes fitted additive payload: x² do2→4, not OLS1.36; LINEAR1+3X→7; complete fact X1/Y1.25 preserves residual.25 and shared-world ITE3. Independent degree3 helper gives query8/counter8.25/ITE3.25. Removal `_polynomial_predict` retains coefficients/markers but2FAIL, linear1PASS. Original B222 does not require commissioning a new default nonlinear fitter; partial nonlinear posterior remains limited/non-gating.

**Version companion.** VERSIONeaf9/docs e94 current default/catalog/snapshot/CAS1.1 agree; missing/explicit historical1.0 remain1.0 without worker authority upgrade. Genuine64-row gcm worker, public class identity/pickle/CAS, native15PASS/independent9 adversaries and retained-marker version removals measured. Constructor default change declared breaking; old CAS compatibility is explicit. Full generator FAIL for other feedback nested refs is not SCM-ownPASS or P41 inheritance.

**Limits.** Finite empirical/affine/additive univariate polynomial profiles; no interaction-polynomial generality, arbitrary nonlinear posterior or real model authority. Version/schema companion does not reopen/close all scientific IDs by itself.

<a id="f-m11"></a>

### F-M11 — Surgical planning and stochastic-law tail oracle

**IDs.** B224/B225. Replaced natural mechanism bypass and pruning preserve relevant factual ancestors/shared noise; unknown policy law never silently becomes atomic do. Existing Normal/Uniform/TruncNormal/explicit atomic static profiles bind parameters/seed/support.

**Independent oracle.** Original `test_scm_result_semantics.py@6dcb792b6f8c2d2dcfc04a5e04ea33135a2ad181:L222–250` computes Normal CDF with **math.erfc**, and positive-tail conditional CDF from survival-function differences, including [8,9] and [-12,-10]. It is independent of sampler SciPy; prior «independent SciPyCDF» label is corrected, not a new581-test run.

**Negative/limits.** Invalid scales/nonfinite/unknown syntax/support refuse; continuous truncated tails cannot collapse into endpoint atoms. Full-graph/action oracle, reorder/irrelevant-node and law-removal controls retain original source. Static compact lag/unknown posterior refuses; no universal stochastic family/temporal/production-authority claim.

<a id="f-m12"></a>

### F-M12 — Original Treasury, family/IC and native IR layout migrations

**IDs.** LA-001/LA-002/LA-037 have separate original acceptance. Treasury03bb/63425 real compile root→salts32-word fold→native RNG/public execution proves seed/order/replay; versioned v1 intentionally preserves same node draw steps0/1, legacy plans preserve old law.

**FAMILY7f/docs3e181.** Four canonical family IDs/assumptions/parameters and unknown-ID refusal; actual IC service→IR certificate CAS/fresh reader; five real descriptors/class resolutions, four typed unsupported execution refusals. Original family specification need not be executable: optional four family→state kernels are not a closure prerequisite. Nonmonotone tax/wrong payment actual negatives and catalog/family-owner removal FAIL.

**LA-037 consumer.** Native IR five object/builders, direct Trinity binding, both known wrappers direct toIR, native income_tax→layout→patch/state/CAS; real maintained page with three Python directives and five layout anchors. Installed wheel/sdist each13PASS only for exactly byte-identical three IR owner/wrapper files, not newly installed Treasury/monitor behavior. Layout-body removal fails actual consumers even with builder/type markers.

**Limits.** Original finite LA-002/037 migration complete; strict full docs/architecture/production gates separate. Compatibility addresses stay supported until their owner lifecycle decision; no invented retirement date or new economic law.

<a id="f-m13"></a>

### F-M13 — LA-003 equivalent relocation with preserved fiscal/labor law

**Original criterion.** Registration/spec, string class paths, PatchMap/active-target masks/fiscal balance/employer IDs/firm labor counts/PRNG progression/compiler/replay and existing fiscal/labor/gradient tests. Relocation preserves old ID/fingerprint; changed economic law needs its own version.

**Current evidence.** ECO412 actual registry→compile→CAS→execute→apply_patch_map/load snapshot and adapter→native consumers compare complete patches/masks/accounting/count/key under finite equivalent fixtures; deliberate plugin-law divergences are LA-004, not relocation failure. Fiscal debit removal5FAIL/2outsidecontrolsPASS. Original whole LA-003 remains **limited** because actual decimal .10 fiscal budget precision gives1000.0000149011612 vs1000 in broader97; tolerance/law not altered to hide it.

**Separate numeric companion.** CARRYc003 temporal output cast to incoming state dtype, actual abstract PPO-loss promoted carries and declared MetricsBuffer storage casts fixes two real train/ES dtype failures; own37PASS +independent37PASS. It does not decide fiscal decimal arithmetic, production calibration or universal migration equivalence. P41 remains not_established for overlapping broader gate.

<a id="f-m14"></a>

### F-M14 — LA-004 distinct models; LA-035 historical baseline and intent

**LA-004 original acceptance, closed finite profile.** Native reported-income flat tax updates income/government.balance and threshold labor/employer/count/key; EconomicsPlugin progressive wealth tax and find/separation/wage dynamics operate on EconomicState. ECO412 full state/units/time-step/taxbase/RNG/budget mapping, deliberately equal regimes **and** deliberate divergence, accounting/seed/observables actual producer→consumer proofs satisfy this criterion. Richer plugin is not drop-in replacement; no welfare normative choice is needed to establish inequivalence.

**LA-035 remains held.** Original `-mean(income)/max(mean(abs(income)),1)+10·budget_penalty`, min_balance−1000, all population entries, aliases/nativeGlobalState/JIT/grad/numeric guards preserved. Nonnegative mean≥1 remains exactly−1 at every scale; not silently income maximization. Named optimizer/source-config/FQN caller and semantic units/population/time/sign intent are not established. Minimum owner packet in ECO check15 `author/economic-owner-packet.json`; no new welfare convention or interpretation is invented.

**Separate Gini property, no new ID.** Existing @foundry-owners numeric-guardrails decision admits classical Gini only on finite nonnegative active resources. Current canonical hard calculator/admission used by aggregate/PureExecutor, objectives, plugin/report API and enumerated live readers; signed simulations remain allowed with Gini disabled. Stale finite cache does not license current[-2,1]/[-1,2]. Dated DistributionAwareExecutor snapshot retains last_update_step and historical meaning. Current dtype metadata/float32storage precision preserved, equations/norm/weights/RNG unchanged. Known pairwise scale/zero-resource/JIT/registeredconsumer/removal proofs do not close LA-035 intent or LA-003 fiscal precision.

<a id="f-m15"></a>

### F-M15 — Lex norm diff and topic hypotheses without effect/authority promotion

**ID.** LA-017 finite pass-plan dedupe/source binding,CAS/CLI witnesses on Lex00a6 retained. Actual ExprAST, config/report identity and duplicate first occurrence property measured; full supported caller/config/corpus migration reconciliation remains limited, not completed by dedupe alone.

**Interpretation.** Source/effective-date/legal authority, textual obligation diff, candidate topic similarity and causal effects are distinct. Synthetic NormPack/StubBackend transport does not prove current-law authority; missing institutional authority is not by itself a prerequisite to a generic synthetic migration test. No current law/real effect claimed; real-data-dependent packet stays local G.

<a id="f-m16"></a>

### F-M16 — Supported public causal facade ABI and current packet boundary

**ID.** LA-020; LA-007/019 supported package consumers separately. Historical API729 actual49native, wheel/sdist48PASS/1Git-censusdeselection each, complete literal/computed-input denominator and exact package byte identity remain source-specific. Object/FQN/pickle/docs/monkeypatch consumers require canonical identity, not no-reflection count.

**Current pending.** New API generic supported-export/annotation guard and source/loader/docs/install owner packets require their own frozen review/receipt. Do not adopt an uncommitted source or an independent BLOCK as current PASS; 182 computed candidates are inputs to classify, not proof that every expression or hypothetical external client is supported.

**Negative/limits.** Clone/export/bridge removals with identical labels must fail actual consumer calls. Exact empty siblings already absent198; preserve nonempty packages. No blanket arbitrary third-party private ABI guarantee, full hosted docs/authority acceptance or P41 inheritance from overlapping failures.
