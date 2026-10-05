# Численные методы: решения, которые должны дать функцию

Goal: восстановить математически корректную поддержанную функцию на canonical
owner, сохранить provenance и consumer semantics, уменьшить цену сопровождения.
Ни библиотека, ни валидный DTO сами по себе не устанавливают admissibility.

## Уже проверенные методологические разграничения

| Свойство | Выбранное направление | Почему / проверка |
| --- | --- | --- |
| CAU-03/B210: robust bias correction в RDD | Тонкий адаптер настоящего `rdrobust` для corrected profile; текущий uncorrected local polynomial оставить явно отдельным. | Пакет реализует correction вместе с соответствующей inference; в задаче должны быть curvature, heteroskedastic DGP, ненулевая correction и coverage. Квадратичный fit и отказ corrected mode не реализуют RBC. [Официальный rdrobust](https://rdpackages.github.io/rdrobust/). Target-runtime профиль ещё требуется фактически проверить. |
| BER-01/LA-036: conditional explanation | Bound conditional sampler over admitted source law; обычный KernelExplainer допустим только для объявленного replacement/marginal профиля. | Его documented background masking заменяет отсутствующие признаки значениями background rows. Это не общий conditional sampler при зависимых признаках. Контроль: correlated Gaussian, где conditional и replacement coalitions дают различные Shapley values. [KernelExplainer API](https://shap.readthedocs.io/en/stable/generated/shap.KernelExplainer.html). |
| UQ / Sobol low-discrepancy generation | Использовать уже доступный SciPy QMC и валидировать фактический sampling design; статистическую error estimate получать по корректным independent scrambles/репликациям. | `random_base2` сохраняет balance при 2^m; skip/thinning/arbitrary n могут лишать последовательность этого свойства. Это не запрет любых n, а запрет приписывать им гарантию balance. [SciPy Sobol](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.Sobol.html). |
| Causal estimation vs identification и interval inference | Расширять существующий typed causal owner, подключая выбранный estimator по его estimand/assumptions. | DoWhy разделяет model→identify→estimate→refute. EconML DRLearner задаёт cross-fitting и inference profiles; библиотечный вызов не подтверждает истинность causal graph и не делает каждый flexible learner CI достоверным. [DoWhy](https://arxiv.org/abs/2011.04216), [EconML DR](https://econml.azurewebsites.net/spec/estimation/dr.html). |

Таблица — proposed engineering choices. Перед публикацией corrected profile
его owner закрепляет backend version, actual parameters, dtype, source inputs,
fit/split seeds, среду и полный runtime call. Пока этого нет, профиль остаётся
`UNRUN`/unsupported с точной причиной; это не основание возвращать пакет как
полностью выполненный.

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

Решения ниже выбраны для следующей реализации. Численные oracles — спецификации проверок, не новые PASS. Детали deployment находятся в runtime-profiles; одинаковые источники закона и persisted поля должны следовать одному semantic решению, а не расходиться по веткам.

<a id="methods-c"></a>

## C — выбранные методы

<a id="c-m1"></a>

### C-M1 — BERL conditional Shapley: verified Gaussian law, exact law / approximate MC expectations

**Выбранное решение.** Implement as a full conditional capability: verified joint-law binding -> supported conditional draw/expectation producer -> existing coalition/Shapley executor -> versioned persisted ExplanationBundle -> Runtime and Phase5 readback. The Gaussian conditional distribution is analytic; only coalition expectations with an analytic model oracle are exact. Finite draws for general nonlinear models are approximate Monte Carlo estimates with declared precision. Standard KernelExplainer is not the conditional sampler. Keep current diagnostic/refusal behavior until that path exists.

**Библиотека и собственная часть.** Reuse BERL's existing coalition enumeration and persist/readback contracts. SHAP KernelExplainer uses background rows to integrate out absent features; it does not infer P(X_not_S | X_S) from correlation. Own the small conditional Gaussian draw provider and feed its expectation into the existing executor; do not fork a second Shapley engine or treat a masker/dependence label as a law.

**Закон и область поддержки.** For a content-resolved, verifier-admitted source/model whose Gaussian family, feature variables/order, observed population/cohort, epoch/time, schema, and support all match this request, compute mu_notS|S = mu_notS + Sigma_notS,S Sigma_SS^+ (xS-muS) and Sigma_notS|S = Sigma_notS,notS - Sigma_notS,S Sigma_SS^+ Sigma_S,notS. A covariance matrix or normal-family label alone is not source/family admission. Validate finite values, symmetric PSD covariance, exact variable/order mapping, and xS in singular support; preserve null spaces and refuse inconsistent support rather than silently adding jitter. The conditional law is analytic; finite floating-point computations carry numerical tolerances.

**expectation_estimator.** For affine/linear f with an analytic coalition oracle, compute v(S) and Shapley values analytically and label them exact within declared floating-point tolerance. For general nonlinear f, finite conditional draws give approximate estimates of each v(S); declare sampler, seed, min/max draws, absolute and relative tolerances, confidence procedure/level, and stopping rule (for example CI half-width <= abs_tol + rel_tol*abs(estimate)). Persist per-coalition draws, estimates, uncertainty/half-width and achieved tolerance; propagate the sampling design to Shapley uncertainty. If max_draws is reached first, emit precision_not_met/limited, never exact. This is a probabilistic precision statement under the named procedure, not a deterministic universal error bound. If high-dimensional coalition/permutation sampling is used, record its separate budget, seed, uncertainty and tolerance.

**Независимый oracle.** Exact analytic fixture: for (X1,X2)~N(0,[[1,.8],[.8,1]]), f(x)=x1, x=(1,1), conditional coalition values (0,1,.8,1) yield Shapley (.6,.4), with no Monte Carlo tolerance. At rho=0 conditional and marginal both yield (1,0). For a nonlinear f, compare finite-draw coalition estimates against an independent analytic or quadrature oracle under the same admitted law and assert the declared confidence/tolerance behavior, including a max-draw precision_not_met case.

**Negative controls.** Same correlated case through marginal-background KernelExplainer yields (1,0), so it must fail a conditional oracle despite matching field names and method label.; Reject changed law bytes/digest under the same caller ID, covariance without resolved source/model/population/epoch/verifier binding, wrong variable order/schema, asymmetric or materially indefinite covariance, impossible singular-support observation, stale model/population epoch, and absent law; do not fall back to marginal or independence.; For nonlinear f, remove MC uncertainty/tolerance metadata, claim exact after stopping before tolerance, or exceed max_draws without precision_not_met; the numerical acceptance/readback must fail. Keep expectation MC diagnostics distinct from Shapley permutation-sampling diagnostics.; Reopen the persisted bundle in both actual consumers and remove the conditional producer while retaining metadata markers; the positive conditional gate must fail.

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

## F — выбранные методы

<a id="f-m1"></a>

### F-M1 — Typed causal uncertainty: separate outcome/ITE distributions, posterior credible intervals, and estimator confidence intervals

**Finding IDs.** B215; B223

**Свойство.** A CI is a sampling-distribution statement about an estimator; quantiles over outcomes or individual effects are distributions, not CI bounds. A Bayesian posterior interval is a third meaning and must keep its posterior/model lineage.

**Сегодняшнее расхождение.** Stochastic GCM and twin paths derive bounds from outcome/ITE draws yet pass through the common causal uncertainty IR as BOOTSTRAP plus CONFIDENCE_INTERVAL, is_heuristic_ci=false, and sometimes gate_eligible=true. Fixed-fit predictive draws and heterogeneous ITE draws do not resample/refit the estimator. The shared IR's default semantics let the consumers confuse these meanings.

**Выбранная реализация.** Correct the common IR/producer/consumer path as one change: add or use distinct typed result kinds for predictive outcome distribution, ITE distribution, posterior credible interval, and estimator CI; keep GCM/twin draws in the first two kinds. For a frequentist GCM/twin CI, add a declared iid-unit nonparametric bootstrap that resamples observational units, refits every mechanism/model, recomputes the same target estimand, and derives the interval from the replicate estimators. Persist resampling unit, refit scope, seed, replicate count, target, and coverage profile. Do not promote until actual CAS readback consumers enforce the kind.

**Отвергнутый вариант.** Do not call more draws from a fixed fitted model a bootstrap; do not rename percentile output or set confidence markers to manufacture inference; do not make all uncertainty unavailable when a supported refit profile can be implemented.

**Canonical paths.** policy-engine/src/polisyos/ir/analytics/uncertainty.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/src/polisyos/ir/analytics/causal_queries.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/src/polisyos/ir/analytics/twin_network.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/src/polisyos/foundry/methods/catalog/causal/twin_network_query.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/foundry/methods/catalog/causal/test_gcm_query.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/foundry/methods/catalog/causal/test_twin_network_query.py@97c85fae2d4505ec8248540d98b9556296244208

**Зависимости.** No new library for the semantic correction. The bootstrap requires stable source-bound iid unit rows, deterministic refit seed/schedule and a consumer that reads the persisted typed result. The optional DoWhy runtime is not installed in the cited Python 3.14.2 baseline.

**Положительная функция и независимый oracle.** For exact Gaussian abduction, U~N(0,1), Y=U+epsilon with epsilon~N(0,1), observe Y=2: posterior U|Y=2 is exactly N(1,0.5); compare the posterior credible interval to that analytic distribution and keep it tagged posterior. Separately, on an iid known-effect SCM, refit-bootstrap ATE CI over independent dataset replicates should achieve its declared approximate coverage profile; doubling sample size should shrink estimator-CI width roughly by sqrt(2), while fixed-model predictive span stays stable.

**Различающий negative.** Hold fitted model/data fixed and multiply the number of predictive draws by 100: the output distribution can stabilize but must remain ineligible as estimator CI. A fake BOOTSTRAP/CI marker with percentiles from the same fixed model must fail the fresh-reader gate. Make two observed treatment levels share a perfectly correlated unit effect: the ITE distribution is not its sampling CI.

**Границы.** The exact Gaussian posterior applies only to the specified conjugate SCM. A refit bootstrap is an approximate sampling interval under iid sampling and a fixed identified graph/estimand; it does not establish unmeasured-confounding assumptions or universal finite-sample coverage. Keep all such output candidate/limited until input law, fit failures and gate consumer are bound.

**Runtime.** No new package is needed for IR semantics. GCM bootstrap execution cost and the target DoWhy/NetworkX Python combination were not measured; the optional backend receipts are skip/UNRUN, not runtime PASS.

**Основания.** policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/graph-scm.json@85c16de9f16a4e21c05c516271b6c81e08b7a39f#sha256=4c4bd3eb636a9e460c2fd239adbdc1a238463315d4c0899ba0bc8e6d4e4f3050; [первичный источник](https://github.com/py-why/dowhy/blob/main/dowhy/causal_estimators/linear_regression_estimator.py)

<a id="f-m2"></a>

### F-M2 — Cross-fitted TMLE and nuisance cache/resource contract

**Finding IDs.** B54; B56

**Свойство.** Treatment-effect targeting must match the declared outcome family/estimand; nuisance cache identity must bind source data, folds, model, seed and fit options; execution must stay within the orchestration budget without omitting folds.

**Сегодняшнее расхождение.** G97's cache hashes data/config and its tests exercise fresh diagnostics, but __shared_nuisance_key remains caller-asserted. The fold worker default is task count rather than the global runtime cap. TMLE's fluctuation is identity-link for all outcome families, and its normal EIF interval plus overlap/ESS widening is asymptotic/custom rather than a general finite-sample coverage guarantee.

**Выбранная реализация.** Retain the canonical cross-fit/TMLE owner; use an outcome-family-specific fluctuation (logit fluctuation for binary/bounded Q, identity only for its stated continuous profile), preserve the score equation and fold lineage, and bind the shared-cache key to a recomputed content/config identity. Wire the existing global worker budget into fold scheduling. Use an EIF normal CI only for the declared regular, positivity-supported iid profile; do not add a black-box package as a substitute for target/consumer semantics.

**Отвергнутый вариант.** Do not accept a supplied cache key as provenance; do not clip a binary prediction then claim the same unconstrained identity-link update; do not use cross-fitting or a 'coverage guard' alone as proof of coverage.

**Canonical paths.** policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/src/polisyos/foundry/methods/catalog/causal/nuisance_layer.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/foundry/methods/catalog/causal/test_tmle_fit_contract.py@ef3f208db031671d9f0d5cefe1ffa68af0650f0a; policy-engine/tests/unit/foundry/methods/catalog/causal/test_nuisance_resolver_wiring.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/remediation/test_fit_01.py@97c85fae2d4505ec8248540d98b9556296244208

**Зависимости.** Current path uses existing NumPy/sklearn-compatible nuisance backends. Receipt ran 33 selected tests, but DoWhy/EconML optional backends were absent/UNRUN. The orchestrator worker budget is a required runtime input, not a new dependency.

**Положительная функция и независимый oracle.** Known binary-outcome DGP with randomized A, one measured confounder W, known Q0/Q1 and nonzero ATE: compare estimate to analytic population ATE, targeting fluctuation score to zero, every Q prediction to [0,1], and output lineage to exact held-out folds. Repeat at declared overlap profile to estimate empirical coverage with a stated Monte Carlo tolerance.

**Различающий negative.** Binary Q predictions at 0.01/0.99 plus a deliberately poor initial fit must not leave [0,1] after targeting. Same supplied __shared_nuisance_key with altered data/fold IDs/model options must miss cache. Exceed worker budget pressure while retaining every fold; a green result from omitted folds fails.

**Границы.** EIF normal inference is asymptotic and requires iid independent units, regularity, positivity and appropriate nuisance behavior. No interval is gate-eligible under observed positivity failure, unresolved target identity, or unsupported outcome law. Source receipt validates code probes, not domain-wide estimand coverage.

**Runtime.** No added package is required in this profile. The execution budget wiring and a full actual consumer replay are still needed after integration; no runtime command was run for this audit.

**Основания.** policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/fit-tmle.json@ef3f208db031671d9f0d5cefe1ffa68af0650f0a#sha256=2e6e0c9997dc8f9ee80c3cc273ea84572b78189c3dfcf17c88a9d1db1aee9fc3; [первичный источник](https://onlinelibrary.wiley.com/doi/10.1155/2014/502678); [первичный источник](https://doi.org/10.1111/ectj.12097)

<a id="f-m3"></a>

### F-M3 — Two-period DiD estimator and parallel-trend diagnostic

**Finding IDs.** B204; B205; B206

**Свойство.** For supported 2x2 input, interaction coefficient is the declared DiD contrast; inference must use the declared independent sampling unit. A diagnostic with too few preperiods is not evidence that parallel trends passed.

**Сегодняшнее расхождение.** G97 correctly rejects t0=0 and computes the 2x2 interaction with HC1 or unit-cluster CR0. However _parallel_trend_diagnostic returns passed=true with p_value=None for t0<3. Cluster CR0 with normal critical values has no small-cluster finite-sample guarantee. Dedicated and umbrella callers must share the confidence-level/contrast semantics.

**Выбранная реализация.** Keep the direct interaction OLS owner and explicit HC1 iid-row vs unit-cluster CR0 profiles; replace boolean pretrend result with not_testable, evidence_of_violation, or no_detected_pretrend. Make pretrend evidence a declared limitation, never a gate proving the identifying assumption. Add a separately named small-cluster method only if its actual correction is implemented and independently checked.

**Отвергнутый вариант.** Do not treat insufficient preperiods or non-rejection as proof of parallel trends; do not label HC1 as clustered or CR0/z as finite-sample correct for any cluster count.

**Canonical paths.** policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/foundry/methods/catalog/causal/test_did.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/remediation/test_cau_01.py@97c85fae2d4505ec8248540d98b9556296244208

**Зависимости.** No new library; a separate statsmodels reference was exercised in the CAU development environment. The original shared environment had a statsmodels collection error; DoWhy cells were skipped.

**Положительная функция и независимый oracle.** Synthetic 2x2 panel with known ATT=3 and at least three preperiods with zero differential pretrend: compare coefficient/covariance to an independent group-labeled statsmodels design and hand-derived 2x2 means; confidence level 80/95/99 must change bounds monotonically.

**Различающий negative.** Set t0=0 (rank deficiency) and t0=1/2 (diagnostic underpowered): first must be INPUT_INVALID, latter not_testable, never passed. Reassign one unit's cluster label and ensure clustered variance changes while HC1 does not pretend to be cluster robust.

**Границы.** Causal ATT still requires conditional parallel trends/no anticipation/appropriate composition; a pretrend test cannot establish those assumptions. CR0/z is a large-number-of-independent-units approximation only; small cluster count and serial dependence need a separately validated profile.

**Runtime.** NumPy/statsmodels profile has a recorded separate environment PASS; statsmodels availability in the original shared runtime failed collection. Do not promote that environment gap to product failure or call skipped DoWhy PASS.

**Основания.** policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/cau-cohort-admission.json@08aaccebfce37aa652ff243fce8037ff48020807#sha256=561a89549fe513551a793b3cc07587c2d652d51cb170c0b619b4dd39e39a6e0c; [первичный источник](https://arxiv.org/abs/1803.09015)

<a id="f-m4"></a>

### F-M4 — CAU-05 dedicated DiD method ownership and caller migration

**Finding IDs.** LA-016

**Свойство.** A dedicated method route must preserve the prior effective estimator inputs/output while removing the deprecated umbrella as the active owner; package presence alone is not caller retirement.

**Сегодняшнее расхождение.** The source has dedicated DiD code/metadata, but the handoff does not establish a full live old-slot caller census, route cutover or actual retirement. This is an ownership/bridge gap separate from the DiD math in B204-B206.

**Выбранная реализация.** Keep one canonical dedicated DiD owner. Enumerate all dispatch plans/importers; migrate each with identical effective estimand, cohort, confidence, covariance and persisted output, then remove the old route only after actual imported consumers prove the retirement.

**Отвергнутый вариант.** Do not infer closure from equal wrapper outputs, a dedicated filename, or constructor-only identity tests; do not keep two independently evolving implementations.

**Canonical paths.** policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/remediation/test_cau_05.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/foundry/methods/catalog/causal/test_did.py@97c85fae2d4505ec8248540d98b9556296244208

**Зависимости.** No external library. Needs complete actual dispatcher/import/caller inventory and a CAS/native reader path.

**Положительная функция и независимый oracle.** For every enumerated legacy caller, compare the actual dispatched canonical method, typed parameters, persisted output and fresh-reader values against a hand-calculated 2x2 DiD fixture; removing legacy route after migration leaves all callers resolvable.

**Различающий negative.** Rewire one real consumer to the old slot and remove the old route: migration acceptance must fail. Change confidence level or cluster labels while keeping route names: output binding must detect the effective input difference.

**Границы.** This proves route/ownership semantics only; it does not validate parallel trends, covariance coverage, or identification assumptions.

**Runtime.** No external runtime requirement; dispatcher discovery and artifact consumer must run in the actual integration runtime.

**Основания.** policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CAU-05.md@c40d4acae1ce58b597267255026d9356565828fd#LA-016

<a id="f-m5"></a>

### F-M5 — Staggered DiD: θ_sel cohort-size target with unit-shared studentized Mammen multiplier

**Finding IDs.** B207; B208; B209

**Свойство.** Estimate one predeclared scalar target from eligible ATT(g,t) cells. Point estimate, influence function, null test and interval must represent the same target; one multiplier is shared across all cells for each independent panel unit. Anticipation-contaminated controls are ineligible.

**Сегодняшнее расхождение.** G97 has bounded anticipation eligibility and one shared unit multiplier, but its bootstrap percentiles are descriptive. It computes the current θ_W-style cell-size aggregation, holds weights fixed in draws and labels coverage/p-value not_established; the old absolute-bootstrap-versus-observed comparison is not a null test.

**Выбранная реализация.** Use the Callaway–Sant’Anna within-cohort post-period average, then ever-treated cohort-share aggregate. Declare a fixed study horizon and eligible-period set E_g per cohort before inference; K_g=|E_g|; τ_g=K_g⁻¹ Σ_{t∈E_g} ATT(g,t); π_g=P(G=g | G<∞); θ_sel=Σ_g π_g τ_g. Estimate π_g from the sample and include its ratio-estimation term. For the fixed population target, ψ_i^θ=Σ_g π_g ψ_i^{τ_g} + 1{G_i<∞}/p_E·(τ_{G_i}−θ_sel), p_E=P(G<∞), with ψ_i^{τ_g} the influence function of that cohort’s within-period-average ATT functional. Do not substitute only fixed cell weights or omit the cohort-share term. On n independent panel units, use iid Mammen multipliers V_ib, shared by unit across every cell, with values (1−√5)/2 and (1+√5)/2 and probabilities (√5+1)/(2√5) and (√5−1)/(2√5). Form θ*_b=θhat+n⁻¹Σ_i V_ib ψhat_i^θ, σhat²=n⁻¹Σ_i(ψhat_i^θ)², Z_b=√n(θ*_b−θhat)/σhat. For H0:θ=θ0, Tobs=√n(θhat−θ0)/σhat; p=(1+#{|Z_b|≥|Tobs|})/(B+1). The two-sided 95% interval is θhat ± q_.95(|Z_b|)σhat/√n, inverting this same scalar test. Pointwise scalar inference is the default; simultaneous bands are a separate profile.

**Отвергнутый вариант.** Do not let longer-exposed cohorts gain extra weight through θ_W when θ_sel is the declared target; do not treat estimated cohort shares as fixed without declaring a different conditional target; do not renormalize E_g separately inside each draw; do not use noncentered percentile estimates for a null p-value; do not leave pairs bootstrap and IF multiplier as unresolved alternatives.

**Canonical paths.** policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/foundry/methods/catalog/causal/test_did.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/remediation/test_cau_02.py@97c85fae2d4505ec8248540d98b9556296244208

**Зависимости.** No new package. Requires row-identity-bound panel units, fixed E_g/horizon, cohort shares, valid cell IFs, shared seeded multipliers, persisted target/statistic metadata, and the actual fresh-reader causal-output consumer.

**Положительная функция и независимый oracle.** Use a known staggered panel DGP with at least two unequally sized cohorts, unequal follow-up lengths, nonzero cohort/time effects, never-treated controls and no anticipation. Compare every ATT(g,t), θ_sel and its estimated-share IF term to an independently derived oracle; ensure the result differs from θ_W when cohort follow-up lengths/effects differ. Repeat seeded null and alternative samples to assess pointwise size and 95% coverage with binomial Monte-Carlo bounds. Change only the declared E_g/aggregation and verify the target change is preserved through CAS and a fresh consumer.

**Различающий negative.** A zero-effect DGP must not produce p≈1/2 merely because an uncentered bootstrap estimate is compared with the observed estimate. Delete the estimated cohort-share IF term while retaining all field names and require the heterogeneous-cohort oracle to fail. Change E_g, cohort identity or unit multiplier alignment while preserving result markers and require consumer binding to reject. A treated-during-anticipation control is excluded; setting anticipation to zero is the positive control.

**Границы.** Large independent-unit asymptotics only; no small-cluster guarantee, serial dependence beyond the sampling-unit cluster, simultaneous familywise band or universal parallel-trends claim. Conditional parallel trends, no anticipation, common support and no interference remain identifying assumptions. Fixed E_g/support failure produces a typed limitation, not draw-specific redefinition of the target.

**Runtime.** Current NumPy/Python route is sufficient. Existing receipt validates the bounded cohort/anticipation behavior, not B208 null size or coverage; no tests were run for this mathematical decision.

**Основания.** policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/cau-cohort-admission.json@08aaccebfce37aa652ff243fce8037ff48020807#sha256=561a89549fe513551a793b3cc07587c2d652d51cb170c0b619b4dd39e39a6e0c; policy-engine/_build/e02-g-closure-research-20261005/F-plan-independent-review.md#sha256=9e097992caad9de84c237e1d33458b2cb6b13b0067d8cfb0f0826eaaef6779e6; [первичный источник](https://arxiv.org/abs/1803.09015)

<a id="f-m6"></a>

### F-M6 — Sharp RDD: pinned rdrobust RBC profile, with explicit GPL distribution decision

**Finding IDs.** B210; B211

**Свойство.** The inferential result must be a robust bias-corrected sharp-RD estimate and interval, accounting for leading-bias estimation in both point and variance. O(np) memory is a separate performance property.

**Сегодняшнее расхождение.** G97 vectorizes weighted least squares to avoid an n×n matrix but retains homoskedastic WLS covariance. bias_correction is not RBC; its bandwidth is explicitly IK-like MVP and its count-ratio density diagnostic is not McCrary. No typed treatment-received vector supports fuzzy LATE.

**Выбранная реализация.** Scientific reference/profile: official Python rdrobust==2.1.0, source commit 4322d4f57ce653668043f9bb262f00bbc2423554 and universal wheel SHA-256 8179f8f75445876297317a9805b81cbbf2e1e39bf804a460a8c23d0d7fa33263. For sharp RD bind tau_bc, the robust se.rb value (not se.us), and the robust CI row (not the bias-corrected point with conventional SE); persist echoed cutoff, p, q, h, b, kernel, vce, level, masspoints, bandwidth selector and source/data identity. Package metadata reports GPL-3.0-only; policy-engine/LICENSE is proprietary, so the distribution owner must explicitly choose whether the package may be shipped. A subprocess is not assumed to settle that license decision. If package distribution is declined, implement the published CCT RBC formulas as a finite alternative task and use rdrobust as an external differential oracle only under an approved test/dependency arrangement; do not leave RBC indefinitely unsupported. Keep current conventional sharp local-linear as a separately named method. Fuzzy/LATE stays unavailable absent typed first-stage input and independently verified ratio/covariance.

**Отвергнутый вариант.** Do not call quadratic regression, a bias flag, or O(np) WLS a robust bias-corrected CI. Do not select the conventional or bias-corrected-with-conventional-SE row as the RBC interval. Do not infer license permission from process isolation. Do not claim fuzzy LATE from x/y alone.

**Canonical paths.** policy-engine/src/polisyos/foundry/methods/catalog/causal/rdd.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/foundry/methods/catalog/causal/test_rdd.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/remediation/test_cau_03.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/LICENSE@c40d4acae1ce58b597267255026d9356565828fd

**Зависимости.** rdrobust 2.1.0 requires Python >=3.9; PyPI artifact is a universal py3-none-any wheel, but no Python 3.14 target import/consumer run was measured. Resolve exact transitive environment and package/Wheel consumer before runtime claim. Distribution gate: obtain explicit owner decision for GPL-3.0-only package against the proprietary project license. If declined, implement CCT 2014 RBC formulas in project code and retain exact reference version/checksum where its testing use is approved.

**Положительная функция и независимый oracle.** Use source-bound curved left/right regression functions with heteroskedastic noise; compare the application result field-by-field to an independent direct rdrobust 2.1.0 call on identical pinned rows/options, verify tau_bc responds to nonzero leading bias and robust CI uses se.rb. Run at least 2,000 seeded independent null and nonzero-effect draws to evaluate empirical 95% coverage against binomial Monte-Carlo bounds. If own RBC is selected for licensing reasons, use this same direct-library oracle plus the published CCT equations.

**Различающий negative.** Remove only the real RBC producer while retaining settings/markers and require direct-result and repeated-coverage probes to fail. Swap robust and conventional SE/CI rows, alter cutoff/bandwidth/source rows, or omit the license choice while retaining package name; consumer/acceptance must reject. A fuzzy label with no treatment-received vector is invalid.

**Границы.** Sharp RD only. RBC is asymptotic under continuity/local-polynomial and bandwidth assumptions, no manipulation and valid sampling; simulated coverage validates implementation under that DGP, not real-design admissibility. Fuzzy LATE and a real McCrary density test are separate capabilities.

**Runtime.** The pinned wheel is py3-none-any and metadata says Python >=3.9, but the wheel provenance says uploaded with CPython 3.13.14; this does not establish target Python 3.14 behavior. Exact environment install, import, actual producer → persisted artifact → fresh reader consumer, and license disposition are separate gates. No install/tests were run for this decision.

**Основания.** policy-engine/_build/e02-g-closure-research-20261005/F-plan-independent-review.md#sha256=9e097992caad9de84c237e1d33458b2cb6b13b0067d8cfb0f0826eaaef6779e6; policy-engine/LICENSE@c40d4acae1ce58b597267255026d9356565828fd; [первичный источник](https://pypi.org/project/rdrobust/2.1.0/); [первичный источник](https://github.com/rdpackages/rdrobust/blob/4322d4f57ce653668043f9bb262f00bbc2423554/Python/rdrobust/src/rdrobust/rdrobust.py); [первичный источник](https://doi.org/10.3982/ECTA11757); [первичный источник](https://rdpackages.github.io/references/Cattaneo-Keele-Titiunik_2023_SIM.pdf)

<a id="f-m7"></a>

### F-M7 — DoWhy v0.14 linear ATE in an isolated, typed Python 3.12 worker

**Finding IDs.** B212; B213

**Свойство.** Identification, estimator/contrast/target, estimate and interval are distinct typed outputs bound to the actual producer. The selected scalar confidence interval must be shape- and level-validated, not inferred from labels.

**Сегодняшнее расхождение.** G97 wrapper does not explicitly bind control/treatment values or target_units; supported labels include mediation profiles without a demonstrated estimator. The CI parser flattens arbitrary shapes, takes the first two values, and swaps reversed endpoints. DoWhy is absent/UNRUN in the Python 3.14 baseline.

**Выбранная реализация.** Use real DoWhy 0.14 through an isolated Python 3.12 worker dispatched by the existing execution-resource orchestration. This is a selected, scoped cross-interpreter worker extension to F’s original no-parallel-shim prompt under this research recommendation, not a way to claim native Python 3.14 availability. Worker imports no PolicyOS code and has no authority: versioned JSON request/reply binds schema, exact source/data identity, graph, treatment/outcome, adjustment, method/version, contrast, target, and confidence level; its estimate remains a candidate until the application persists the typed result and a fresh reader consumer validates it. Worker call must be CausalModel→identify_effect(proceed_when_unidentifiable=False)→estimate_effect using the returned estimand and method backdoor.linear_regression, control_value=0, treatment_value=1, target_units="ate", no effect modifiers, confidence_intervals=True and method_params={"confidence_level":0.95}; after the call, assert estimate.estimator.confidence_level == 0.95 and explicitly obtain the interval with estimate.get_confidence_intervals(confidence_level=0.95), then bind/validate those endpoints and compare to direct statsmodels OLS alpha=0.05. Do not infer effective level from an echoed JSON request. Validate one scalar interval only: accept exact shape (2,) or (1,2), finite ordered endpoints, and exact bound level; reject extra contrasts/rows, reversed bounds, NaN/Inf and level mismatch without flattening, first-row selection, swapping or repair. Distinguish a legitimate point-only result from malformed interval. Keep CDE/NDE/NIE unsupported until an estimator-specific mediator DGP and actual consumer path exist.

**Отвергнутый вариант.** Do not call a marker or worker import a DoWhy result; do not silently add an unapproved shim inside the shared 3.14 runtime. Do not let a separate process or JSON envelope assert its own provenance/authority. Do not flatten or repair malformed CI output; do not report mediation from the ATE estimator.

**Canonical paths.** policy-engine/src/polisyos/foundry/methods/catalog/causal/dowhy_identify_estimate.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/foundry/methods/catalog/causal/test_dowhy_identify_estimate.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/remediation/test_cau_04.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/src/polisyos/ir/analytics/causal.py@97c85fae2d4505ec8248540d98b9556296244208

**Зависимости.** Lock a separate Python 3.12 worker environment to DoWhy==0.14 and all transitive artifacts; DoWhy 0.14 official package metadata requires Python >=3.9,<3.14 and the wheel SHA-256 is 9c5855d80601e0feb2d0d232c19e7b660db4cd0ea04ace2ebaefcdb3599ab9db. Exact statsmodels and worker dependencies must be locked from the built worker. Integrate only through the existing bounded execution-resource orchestration; do not import worker internals into the application.

**Положительная функция и независимый oracle.** Known linear-confounded DGP: A has conditional positivity given X; Y=2A+1.5X+epsilon with iid Normal(0,1), and no unmeasured confounding. Compare identified adjustment set, ATE=2 and `estimate.get_confidence_intervals(confidence_level=0.95)` exactly with direct statsmodels OLS treatment-coefficient t interval at alpha=0.05; assert `estimate.estimator.confidence_level == 0.95`; repeat independent samples under this Gaussian profile for nominal finite-sample coverage. Bind persisted response to source hash, worker version, estimand/adjustment, values 0/1, ATE target and level; read it from a fresh consumer. Varying contrast/target must change the actual estimator call or be rejected when outside the selected profile.

**Различающий negative.** Unblocked-backdoor/hedge fixture must not identify an ATE; remove a confounder while preserving request labels and require consumer failure. Reject interval arrays with shape (2,2), extra values, reversed endpoints, NaN/Inf or another level. Keep shape markers but replace actual estimate with a stub and require producer/CAS/fresh-reader oracle to fail. A mediation request is unavailable, never a label-only pass.

**Границы.** The exact OLS t interval requires full-rank correctly specified linear constant-effect regression with iid homoskedastic Gaussian errors, valid graph/adjustment, positivity and no unmeasured confounding; it does not prove those causal assumptions. Other outcomes/effect modifiers/estimators need their own validated uncertainty profile. Worker result is non-authoritative and cannot become a publishable claim by itself.

**Runtime.** Python 3.12 worker is an explicit compatibility target separate from G97’s Python >=3.14<3.15 application runtime. DoWhy 0.14 will not install in that interpreter. The actual worker build, execution-resource bridge, persisted artifact, fresh consumer, and affected importer tests are mandatory and not yet run; no backend PASS follows from baseline skips or metadata.

**Основания.** policy-engine/_build/e02-g-closure-research-20261005/F-plan-independent-review.md#sha256=9e097992caad9de84c237e1d33458b2cb6b13b0067d8cfb0f0826eaaef6779e6; [первичный источник](https://pypi.org/project/dowhy/0.14/); [первичный источник](https://github.com/py-why/dowhy/blob/178ecc9c690a02f2801c1f70da2695f5744186cc/dowhy/causal_model.py); [первичный источник](https://github.com/py-why/dowhy/blob/178ecc9c690a02f2801c1f70da2695f5744186cc/dowhy/causal_estimators/linear_regression_estimator.py); [первичный источник](https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.OLSResults.conf_int.html)

<a id="f-m8"></a>

### F-M8 — ADMG m-separation, perfect-do surgery and narrowly named package cleanup

**Finding IDs.** B216; B217; LA-007; LA-019

**Свойство.** ADMG separation uses endpoint marks/collider ancestry; perfect do removes incoming directed and incident bidirected edges while preserving outgoing paths. Package cleanup must target verified empty shims only.

**Сегодняшнее расхождение.** G97 fixes the known reverse-edge normalization and includes finite oracle evidence: 200 three-node ADMGs, 2,400 ordered m-separation queries, plus selected do-calculus consumers. This supports the bounded primitive, not general identification completeness or all PAG extensions. Python package/facade exports have real owners; adjacent directories are not empty-file shims.

**Выбранная реализация.** Keep the compact native ADMG algorithms and their independent latent-DAG/ancestral-moralization oracle for this bounded domain. Use Ananke's m_separated as an optional differential oracle on the same semantics; use NetworkX only after explicit latent-DAG expansion because its API is DAG d-separation. Delete only the exact three verified empty .py shim files, with imports/wheel consumers checked individually.

**Отвергнутый вариант.** Do not project mixed edges into a plain DAG and call it m-separation; do not infer id_engine or Rule1-3 completeness from the finite separator corpus; do not remove directories named like empty files.

**Canonical paths.** policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/src/polisyos/foundry/methods/catalog/causal/do_calculus.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/foundry/methods/catalog/causal/test_admg_latent_oracle.py@85c16de9f16a4e21c05c516271b6c81e08b7a39f; policy-engine/tests/unit/foundry/methods/catalog/causal/test_admg_s_ops.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/foundry/methods/catalog/causal/test_do_calculus_postpass.py@97c85fae2d4505ec8248540d98b9556296244208

**Зависимости.** Current native bounded method needs no graph package. Optional Ananke version and true NetworkX 3.6.1 runtime must be pinned for differential/wheel checks; shared graph environment lacked NetworkX.

**Положительная функция и независимый oracle.** Retain the receipt's finite enumerated three-node ADMG set and compare every query/action set with independently constructed latent DAG expansion plus ancestor-moralization; assert endpoint reversal, collider conditioning and perfect-do edge changes against explicit hand fixtures.

**Различающий negative.** Change only a bidirected edge, collider conditioning set or one removed parent while leaving graph names/markers fixed; native result must differ from oracle. Attempt deletion of a nonempty package directory or import via exact shim path and ensure cleanup consumer detects it.

**Границы.** Finite algorithmic correctness only for enumerated graph sizes/shapes and tested do-calculus forms. Not causal identification, all Rule1-3 contexts, unrestricted PAG/CPDAG extension or domain evidence.

**Runtime.** Receipt: 123 selected checks passed with one optional DoWhy skip; NetworkX was missing in the shared environment and its actual graph contract run had import errors, not a product PASS. Test the supported pinned dependency consumer separately.

**Основания.** policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/graph-scm.json@85c16de9f16a4e21c05c516271b6c81e08b7a39f#sha256=4c4bd3eb636a9e460c2fd239adbdc1a238463315d4c0899ba0bc8e6d4e4f3050; [первичный источник](https://ananke.readthedocs.io/en/latest/ananke.graphs.html); [первичный источник](https://networkx.org/documentation/stable/reference/algorithms/d_separation.html)

<a id="f-m9"></a>

### F-M9 — Mixed graph export immutability and time/PAG boundary

**Finding IDs.** B219; B220; B214; B218

**Свойство.** Persisted/exported graph must preserve typed directed, bidirected and lagged edges/key identity; immutable topology and derived caches must agree after copy. Static DAG consumers may not silently drop time or resolve an ambiguous PAG arbitrarily.

**Сегодняшнее расхождение.** MultiDiGraph supports keyed parallel edge types, deep topology/cache behavior has a bounded implementation slice, known reversed arrows normalize, and static GCM refuses lag edges. B219 remains held because the actual NetworkX exporter/readback consumer did not run in the common environment. Circle-edge rejection avoids false certainty but no general PAG extension or temporal SCM inference exists.

**Выбранная реализация.** Keep typed native edge storage and adapt/export to actual pinned NetworkX MultiDiGraph with round-trip reader checks. For current static GCM, retain explicit refusal on lagged/circle edges. Add a separate time-unrolled (variable,time) profile only if it preserves lag order, initial conditions and horizon; do not claim it in the static method. Resolve one reversed known edge by endpoint normalization; keep ambiguous PAGs set-valued or limited.

**Отвергнутый вариант.** Do not use a lossy DiGraph projection for mixed edges, infer temporal semantics from a filename, drop lag edges, or pick one DAG extension for a PAG without declaring uncertainty.

**Canonical paths.** policy-engine/src/polisyos/foundry/methods/catalog/causal/graph_reconciliation.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/src/polisyos/foundry/methods/catalog/causal/_graph_projection.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/ir/test_causal_graph_contract.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/ir/test_causal_graph_contract.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/remediation/test_grf_03.py@97c85fae2d4505ec8248540d98b9556296244208

**Зависимости.** NetworkX==3.6.1 is the recorded intended consumer version; no actual runtime pass in the shared environment. Temporal expansion is own code and needs a separately versioned schema/profile.

**Положительная функция и независимый oracle.** Round-trip X->Y, X<->Y, duplicate keyed relations, and lag-1/lag-2 through actual NetworkX build, serialize/CAS, fresh read and exported graph; compare immutable adjacency and ancestors cold/warm. On a 4-step unroll, a known lag-1 recurrence must connect only adjacent time slices and be a DAG.

**Различающий negative.** Remove the bidirected edge, merge parallel edges, mutate nested cached topology, or make lag1 indistinguishable from lag2 while leaving type strings: consumer/readback oracle must fail. A CPDAG/PAG circle without a unique extension must return explicit set-valued/unsupported state, not an arbitrary DAG.

**Границы.** B219 held pending actual backend consumer. B220 finite topology/cache contract only. Reversed-edge fix covers the known orientation case; time refusal is not temporal inference and arbitrary PAG identification remains unimplemented.

**Runtime.** NetworkX missing in shared environment; selected graph contract had 15 passed / 11 import errors. Keep this environment nonreceipt separate from product verdict. Build/import on pinned supported runtime before closure.

**Основания.** policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/graph-scm.json@85c16de9f16a4e21c05c516271b6c81e08b7a39f#sha256=4c4bd3eb636a9e460c2fd239adbdc1a238463315d4c0899ba0bc8e6d4e4f3050; [первичный источник](https://networkx.org/documentation/stable/reference/classes/multidigraph.html); [первичный источник](https://networkx.org/documentation/stable/reference/algorithms/d_separation.html)

<a id="f-m10"></a>

### F-M10 — DoWhy GCM actual mechanism fit and persisted SCM producer

**Finding IDs.** B221; B222

**Свойство.** A fitted SCM artifact must be produced by the selected mechanism fitter on source-bound aligned rows, then survive persisted fresh-reader intervention queries. Backend availability or a self-declared mechanism name is not a fit witness.

**Сегодняшнее расхождение.** The GCM path checks whether dowhy.gcm imports but then continues with local NumPy OLS/empirical fitting; nonlinear helper/fixture is not reached on that real fit branch. Aligned empirical roots are carried, but source strings do not authenticate CAS/source data identity. Existing finite tests do not prove a true DoWhy mechanism fit produced the persisted artifact.

**Выбранная реализация.** Use the actual maintained DoWhy GCM producer for this selected method: construct StructuralCausalModel from the validated directed graph; explicitly set each declared root/conditional mechanism class (do not rely on automatic assignment where mechanism selection is ungrounded); call gcm.fit with the bound frame; serialize fitted mechanisms, graph, versions, row/source hash, fit seed/options and supported schema; read it in a new process and answer an intervention query from that persisted artifact. A true DoWhy fit is the functional target, not an import-only fallback. Preserve local fit as a separately named method if needed.

**Отвергнутый вариант.** Do not set dowhy_available and run NumPy code while reporting DoWhy backend success; do not use an auto-selected model label as truth; do not bind empirical samples by axis/length/string ID alone.

**Canonical paths.** policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_fit.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/foundry/methods/catalog/causal/test_gcm_fit.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/foundry/methods/catalog/causal/test_gcm_query.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/remediation/test_scm_01.py@97c85fae2d4505ec8248540d98b9556296244208

**Зависимости.** Pin supported DoWhy, NetworkX, NumPy, pandas, scikit-learn and Python versions as one declared profile. Actual DoWhy installation/wheel fit/readback was not done; the cited default environment marks it absent/UNRUN. Need data artifact source/CAS resolver at fit and readback.

**Положительная функция и независимый oracle.** Generate root X~N(0,1), Y=2X+epsilon with epsilon~N(0,1); bind the exact aligned rows and explicit linear additive-noise mechanism; run actual DoWhy gcm.fit, persist, start a fresh reader, and query do(X=1) vs do(X=0). Oracle ATE=2; verify fitted parameters/residual sampling and consumer result against independently computed least-squares/reference values.

**Различающий negative.** Keep import/version/SCMSpec markers but replace actual gcm.fit with current NumPy helper: backend-provenance consumer must fail. Permute Y rows or change one source hash while retaining vector shape/declared ID: aligned-row binding must reject; remove the fitted artifact before readback and consumer must not recompute a different model silently.

**Границы.** Known-DGP test validates producer binding and one explicit additive-noise SCM; it does not establish graph orientation, causal sufficiency, mechanism selection, or empirical domain effects. Auto assignment quality/independence checks are diagnostics, not proof of graph truth.

**Runtime.** Official DoWhy repository documents StructuralCausalModel -> mechanism assignment -> gcm.fit. Compatibility in the project's target Python 3.14.2 wheel has not been measured. Dependency installation, artifact serialization ABI, and actual consumer are mandatory separate gates.

**Основания.** policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/graph-scm.json@85c16de9f16a4e21c05c516271b6c81e08b7a39f#sha256=4c4bd3eb636a9e460c2fd239adbdc1a238463315d4c0899ba0bc8e6d4e4f3050; [первичный источник](https://github.com/py-why/dowhy)

<a id="f-m11"></a>

### F-M11 — SCM query law admission, exact abduction, and effect distribution typing

**Finding IDs.** B224; B225

**Свойство.** Intervention changes only the target equation; stochastic draws require a declared law, support and query scope. Unsupported stochastic law or temporal query must not silently become atomic do or static inference.

**Сегодняшнее расхождение.** Intervention pruning removes target inputs/descendants correctly and three laws are implemented (normal/uniform/truncated normal). Unsupported law refusal is honest, but does not make generic SCM distribution support complete. The separate B215/B223 uncertainty-semantics defect is assigned to the common IR decision above.

**Выбранная реализация.** Keep the current typed Normal/Uniform/TruncatedNormal static laws and exact surgery; validate each sampler against its analytic CDF/quantiles. Persist law parameters, seed, support and query horizon with the artifact. Refuse unknown laws and static GCM queries over lag edges until an explicitly versioned time-unrolled profile exists.

**Отвергнутый вариант.** Do not generalize one conjugate posterior to arbitrary nonlinear SCMs; do not switch unsupported stochastic law to atomic do; do not call outcome or ITE quantiles a confidence interval or upgrade non-converged inference.

**Canonical paths.** policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/src/polisyos/foundry/methods/catalog/causal/twin_network_query.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/src/polisyos/foundry/methods/catalog/causal/dynamic_graph_dscm.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/src/polisyos/foundry/methods/catalog/causal/space_time_dscm.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/remediation/test_scm_03.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/remediation/test_scm_02.py@97c85fae2d4505ec8248540d98b9556296244208

**Зависимости.** Analytic Gaussian profile uses native NumPy/SciPy routines in the selected path; SciPy is not guaranteed in every runtime extra. DoWhy GCM path depends on the separate actual backend install described above.

**Положительная функция и независимый oracle.** For each declared normal/uniform/truncated-normal structural noise law, compare sampled CDF/quantiles with closed-form values; for Y=f(X,N), verify do(X=x) changes descendants and cuts target inputs while preserving all unrelated equations.

**Различающий negative.** Provide an unknown law, a lagged graph to static GCM, or an unsupported posterior: query must return typed unavailable/limited and remain non-gating. A name/marker for a supported law with an altered sampler must fail the analytic distribution check.

**Границы.** Native stochastic support is limited to the three declared laws and tested static query paths. General nonlinear abduction, arbitrary distribution families, temporal inference and empirical graph identification remain unsupported.

**Runtime.** No target environment run in this review. Preserve separate optional dependency state; import absence and skip are UNRUN. Ensure current supported SciPy/DoWhy versions and query artifact schema are recorded at consumer runtime.

**Основания.** policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/graph-scm.json@85c16de9f16a4e21c05c516271b6c81e08b7a39f#sha256=4c4bd3eb636a9e460c2fd239adbdc1a238463315d4c0899ba0bc8e6d4e4f3050

<a id="f-m12"></a>

### F-M12 — Foundry compiler seed, mechanism activation and installed layout consumer

**Finding IDs.** LA-001; LA-002; LA-037

**Свойство.** Execution randomness, mechanism family and layout must flow from compiler inputs through a persisted artifact into actual state-changing consumer behavior; inventory/class identity alone is not activation.

**Сегодняшнее расхождение.** Compiler tests prove artifact/CAS/layout/family behaviors, but ExecPlan.random_seed=17 can coexist with TreasuryPlan.root_seed=0. Direct randomization helpers accept an explicit seed, so they do not prove compiler binding. Mechanism family inventory is not by itself a live state operation; source import identity is not an installed wheel consumer.

**Выбранная реализация.** Keep native compiler and typed IR. Make one ratified seed source bind to treasury salt and persist the same seed/source lineage; either use the execution seed or explicitly model a separate owner-approved root seed. Wire a family certificate to the actual state operation; prove layout class identity in built wheel/sdist import. Do not replace compiler paths with test-only construction.

**Отвергнутый вариант.** Do not accept matching seed field names when values differ; do not equate registered family with an executable mechanism; do not use source-tree import identity as installed API proof.

**Canonical paths.** policy-engine/src/polisyos/foundry/compile/trinity_compiler.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/src/polisyos/foundry/compile/randomization.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/foundry/compile/test_compile_artifact_contracts.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/foundry/compile/test_randomization.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/foundry/contracts/test_layout.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/foundry/methods/catalog/mechanism/test_families.py@97c85fae2d4505ec8248540d98b9556296244208

**Зависимости.** No new numerical package. Requires canonical compiler, CAS artifact reader, actual execution consumer and built wheel/sdist install/import profile.

**Положительная функция и независимый oracle.** Compile deterministic fixture with seed 17 and known node plan, then read artifact via fresh reader and execute it: every stream salt and certificate must bind seed/source; same seed replays exactly, changed seed changes keyed streams. Registered family must produce its known state delta through actual consumer. Installed wheel exports the exact IR class object identities.

**Различающий negative.** Compile with execution seed 17 and root seed 0 while keeping both field names: fail unless separate seed authority is explicitly declared and cross-bound. Register a family with no executable state transition or remove layout owner from installed package; consumer acceptance must fail.

**Границы.** Deterministic synthetic producer/consumer proof only; no claim about economic validity or real policy simulation. Salt correctness does not prove future randomness quality beyond the tested deterministic contract.

**Runtime.** Current compile receipt had 45 targeted and 14 independent checks, but no installed consumer/wheel run is shown; target packaging and import compatibility remain required.

**Основания.** policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/fry-compile-contracts.json@ea577ac3185829e066a39f51a8a2eae8f1bb5d43#sha256=34c41ca91eab404b3fbdfdba376108f1205ed47010d1e540b7f7b6f960f3e3ca

<a id="f-m13"></a>

### F-M13 — Fiscal/labor kernel migration equivalence

**Finding IDs.** LA-003

**Свойство.** A migration is equivalent only when intended state transitions/patches match under the same typed inputs and random stream, not because similarly named mechanisms or dtypes compile.

**Сегодняшнее расхождение.** Live fiscal and labor kernels operate on WorldState/PatchMap while the Economics plugin uses separate EconomicState/mechanisms; dtype receipt does not compare these producer paths or complete downstream state changes.

**Выбранная реализация.** Keep each canonical execution kernel and plugin as separate owners until matched differential evidence shows a specific contract is equivalent. Build a deterministic adapter only for explicitly ratified equivalent equations; otherwise state separate semantics instead of merging by name.

**Отвергнутый вариант.** Do not treat dtype/construction tests, adjacent class names, or average outcome similarity as migration equivalence.

**Canonical paths.** policy-engine/src/polisyos/foundry/execute/mechanisms/fiscal.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/src/polisyos/foundry/execute/mechanisms/labor.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/src/polisyos/foundry/plugins/economics/mechanisms.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/remediation/test_fry_03.py@97c85fae2d4505ec8248540d98b9556296244208

**Зависимости.** Existing typed WorldState, PatchMap and EconomicState paths; actual executor consumers and seed binding are required.

**Положительная функция и независимый oracle.** For a deliberately equivalent narrow fiscal fixture, hand-calculate tax, subsidy, balance and target mask; run both actual kernel and plugin paths on same state/seed; compare complete typed patches and state invariants, not only averages.

**Различающий negative.** Use wealth-vs-income units and a wage/job-transition fixture; expected distinct outputs prove comparator detects semantic divergence. Perturb only seed and verify stochastic effects are not silently ignored.

**Границы.** Only the ratified equation/state subset can be marked equivalent. No claim of whole-economy policy equivalence from a small synthetic slice.

**Runtime.** No new dependency. Must use actual canonical execution/plugin consumers; source-only comparison is insufficient.

**Основания.** policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/economic-dtype.json@bfc5d0fb8195c2246db72dfb5d46e29a8eec9e42#sha256=c7c0f21acfb3537c9c0a53ef39a36a762193a4b0bb3d0da07bd5c0653f173979; policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/economic-dtype-deciding.txt@bfc5d0fb8195c2246db72dfb5d46e29a8eec9e42#sha256=879ece00b605c674668941c27eb018d15f1dcfd680d25bf7c30359fbc449ff3f

<a id="f-m14"></a>

### F-M14 — Economics score meaning and profile separation

**Finding IDs.** LA-004; LA-035

**Свойство.** A score's units, sign, scale dependence, state variables and audience must match its declared normative/economic meaning; dtype correction does not ratify the objective.

**Сегодняшнее расхождение.** normalized_income_budget_loss uses -mean(income)/max(mean(abs(income)),1)+10*budget_penalty. For nonnegative mean income >=1 the income term is exactly -1 at every income scale; progressive tax/wealth mechanics and live flat income-tax kernel also operate on different state/equation paths.

**Выбранная реализация.** Retain this formula as a separately named historical baseline until its semantic owner ratifies units/sign/normalization. Keep distinct objective profiles for the economic plugin and world execution kernels; add a new scale-sensitive welfare/income objective only after explicit normative owner approval and test the actual consumer.

**Отвергнутый вариант.** Do not silently call the normalized score income maximization or welfare; do not merge wealth and income or progressive and flat tax paths by dtype or name.

**Canonical paths.** policy-engine/src/polisyos/foundry/plugins/economics/baselines.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/src/polisyos/foundry/plugins/economics/mechanisms.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/src/polisyos/foundry/execute/mechanisms/fiscal.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/foundry/plugins/test_economics_dtype.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/remediation/test_eco_01.py@97c85fae2d4505ec8248540d98b9556296244208

**Зависимости.** No new package. A semantic owner decision and actual objective consumer are prerequisites for changing policy interpretation.

**Положительная функция и независимый oracle.** Hand-compute zero, subunit, unit, and >1 nonnegative income vectors plus budget penalties; scale income by 10 and verify the historical ratio is exactly invariant when both means exceed one. Consumer stores the result under the historical profile name.

**Различающий negative.** A purported income-maximization replacement that returns the same score after multiplying incomes by 10 fails a declared scale-sensitive objective test. A wealth vector passed into income objective must be type/unit-rejected or explicitly converted.

**Границы.** Arithmetic and consumer binding only; no normative welfare judgment or empirical economic validity is inferred from synthetic examples.

**Runtime.** Existing dtype path receipt shows 60 dtype tests plus consumer subsets. It does not establish semantic owner signoff or fiscal/labor kernel equivalence.

**Основания.** policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/economic-dtype.json@bfc5d0fb8195c2246db72dfb5d46e29a8eec9e42#sha256=c7c0f21acfb3537c9c0a53ef39a36a762193a4b0bb3d0da07bd5c0653f173979; policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/economic-dtype-deciding.txt@bfc5d0fb8195c2246db72dfb5d46e29a8eec9e42#sha256=879ece00b605c674668941c27eb018d15f1dcfd680d25bf7c30359fbc449ff3f

<a id="f-m15"></a>

### F-M15 — Lexical/legal obligation diff kept separate from causal impact claims

**Finding IDs.** LA-017

**Свойство.** A source-bound normative text comparison may nominate affected topics but does not establish direction/magnitude/population of causal effects or current legal authority.

**Сегодняшнее расхождение.** The frozen NormPack/ExprAST/CAS/CLI route binds the compared inputs, but affected_kpis is heuristic topic similarity. StubBackend/default CLI and synthetic passes are not an admitted law source or a real causal outcome.

**Выбранная реализация.** Keep the exact source/effective-date/authority-backed obligation diff as the Lex owner; name similarity output topic_candidates and make it non-gating. Route any effect claim to a separate causal estimator with independently grounded data and estimand.

**Отвергнутый вариант.** Do not label lexical similarity as measured KPI impact, legal force, or current applicable law; do not promote a stubbed backend because CAS binding passes.

**Canonical paths.** policy-engine/src/polisyos/lex/legal_evaluation/impact_diff.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/src/polisyos/core/components/_cli_lex.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/lex/legal_evaluation/test_impact_diff.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/integration/lex_ir_foundry/test_normpack_factlog_method_bridge.py@97c85fae2d4505ec8248540d98b9556296244208

**Зависимости.** No statistical package. Real source authority/effective date and actual consumer binding are separate institutional inputs.

**Положительная функция и независимый oracle.** Use a frozen synthetic NormPack pair with exact article/version/effective-date identity and hand-authored obligation changes; assert the diff preserves source binding and emits separate candidate topics through CAS/fresh reader.

**Различающий negative.** Paraphrase the same obligation or insert unrelated text with high keyword overlap: candidate topic ranking may change, but no causal KPI estimate or legal authority assertion is allowed. Repealed/out-of-date source and missing source proof must block authority-grade projection.

**Границы.** Textual obligation-change detection only; real legal source grounding and causal effect measurement are out of scope for the lexical heuristic.

**Runtime.** Lex receipt reports native tests and remove-property consumer controls; actual legal corpus/source authority is not in supplied inputs. Stub backend is transport/schema only.

**Основания.** policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/lex-input-binding.json@3fab28d98997527b2a26d46fe4e16220e42383b7#sha256=4f0623168329cfc5c4006c5beb79dc205704beb1dc8b537e47b5d2c09e519c20

<a id="f-m16"></a>

### F-M16 — Causal facade public identity and external consumer census

**Finding IDs.** LA-020

**Свойство.** Facade compatibility means the declared public symbol resolves to the same canonical object through actual package consumers, and removals account for the complete supported caller set.

**Сегодняшнее расхождение.** The candidate verifies 26 selected identity/import cases and preserves canonical symbol identity, but the complete export/import/monkeypatch/docs/serialized-name consumer denominator is not established. Utility judge fails on both measured slice base and candidate, while P41 complete disjoint input census is absent; inherited status is not established.

**Выбранная реализация.** Keep one explicit identity-preserving package facade and canonical owner paths. Complete the actual supported consumer census (public/star/underscore imports, FQN serialization, docs and monkeypatching), then build/install wheel and sdist consumers before retiring any symbol.

**Отвергнутый вариант.** Do not infer all-consumer safety from 26 tests; do not add wrapper clones; do not call a shared base/candidate selector failure inherited without exact slice-base replay and zero intersection across its complete input denominator.

**Canonical paths.** policy-engine/src/polisyos/foundry/methods/catalog/causal/__init__.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/foundry/methods/catalog/causal/test_facade_consumers.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/foundry/methods/catalog/causal/test__causal_engine_contracts.py@97c85fae2d4505ec8248540d98b9556296244208; policy-engine/tests/unit/foundry/methods/catalog/causal/test__interference_contracts.py@97c85fae2d4505ec8248540d98b9556296244208

**Зависимости.** No runtime dependency. Requires full repository consumer enumeration and package build/install readback.

**Положительная функция и независимый oracle.** Build wheel and sdist, install into clean consumer environment, import every enumerated supported symbol through public path and compare object identity to canonical owner. Run representative serialized FQN and documented monkeypatch/import consumers.

**Различающий negative.** Delete one actually referenced export or substitute a wrapper clone that has identical name/signature: installed consumer identity/use test must fail. Demonstrate census script denominator equals the complete tracked caller set.

**Границы.** Only declared in-repository and supported package consumers are covered after census; unenumerated third-party private imports are not claimed compatible.

**Runtime.** Current receipt shows 26 candidate facade checks. Wheel/sdist consumers and complete census remain unperformed; selector base/candidate failure does not establish P41 inheritance.

**Основания.** policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/api-consumer-abi.json@0b6d872d8a681b1725abb5e2e3f57f9668e31c69#sha256=f07ae3db66b8dd4ea34359e059bc5d1bd120b7080188f5b34e978c900de6e388
