# Import Relocations: Nine Rows — Execution Journal

## Fixed slice and initial predicates

- Branch: `codex/import-relocations-nine-seams`, attached.
- Base/readback: `2525da7306d329ae28fa394690e1c39133eb0d55`.
- Git prefix before coordinates: `policy-engine/`.
- Source denominator: complete `src/**/*.py`, 2,600 Python files.
- Canonical source linter: direct exit 1, 42 violations — ARCH001=39,
  ARCH002=1, ARCH004=2, ARCH006=0. Measured `user=8.81s`, `sys=0.71s`;
  uptime 20:33/up 3d10:46 to 20:34/up 3d10:47.
- Independent AST target census: direct exit 0, 39 statements over the nine
  target rows; its pair totals match the canonical report exactly. An initial
  derivation that treated relative imports as roots produced 42 and was rejected
  as a harness non-receipt before any repository edit.
- Release guardrail: direct exit 0 with zero creep. Measured `user=30.54s`,
  `sys=7.02s`; uptime 20:34 to 20:35.
- Package gate: direct exit 1, 151 findings. `finding_count`, list length, and
  unique serialized finding count each equal 151; its fail-closed package
  summary reports current=34, registered=0, unregistered=34. Measured
  `user=59.04s`, `sys=3.33s`; uptime 20:35 to 20:36.

The target pair totals are: `ir -> foundry` 13, `ir -> scientist` 6,
`foundry -> scientist` 5, `lex -> scientist` 4, `core -> scientist` 4,
`lex -> foundry` 3, `ir -> core` 2, `foundry -> lex` 1, and `ir -> jax` 1.

## Frozen pre-edit classification — all 39 statements

Every row below was classified before the first source edit. Result:
`consumer-up`=34, `shared-contract-down`=5, `ambiguous`=0.

| ID | Statement and bound symbols | Shape | Reason / legal owner move |
| --- | --- | --- | --- |
| LF-01 | `lex/interventions.py:17` — `CausalEngine` | `consumer-up` | Lex invokes Foundry causal execution; move temporal execution to the existing upper causal orchestration owner. |
| LF-02 | `lex/interventions.py:18` — `ALearningDTR`, `DoublyRobustDTR`, `OutcomeWeightedLearning`, `QLearningDTR` | `consumer-up` | Estimator selection/execution is Foundry behavior consumed above Lex, not a legal-language contract. |
| LF-03 | `lex/interventions.py:24` — `DynamicTreatmentData` | `consumer-up` | Lex materializes a Foundry protocol DTO; retain neutral temporal declarations and materialize at the upper adapter. |
| LF-04 | `lex/interventions.py:54` — `SearchIteration`, `SearchResult`, `SearchStatus` | `consumer-up` | Lex executes Scientist search and interprets its runtime result; move the adapter to Scientist. |
| LF-05 | `lex/interventions.py:55` — `PolicyCandidateSchema` | `consumer-up` | Candidate validation is Scientist policy-design behavior; Lex supplies compiled legal inputs. |
| LF-06 | `lex/interventions.py:56` — `HierarchicalSearchConfig`, `HierarchicalSearchCoordinator`, `PolicySearchLevel` | `consumer-up` | Hierarchical search orchestration belongs with the existing Scientist coordinator. |
| LF-07 | `lex/interventions.py:1083` — `HierarchicalSearchResult` | `consumer-up` | Lex's return annotation exposes an upper execution result; the adapter and result remain Scientist-owned. |
| LF-08 | `foundry/agent_sim/wiring/contracts.py:22` — `CompiledLexIntervention` | `shared-contract-down` | The model contains only neutral IR intervention/parameter contracts; lower one compiled artifact identity to IR and consume it from Lex and Foundry. |
| CO-01 | `core/components/_cli_metric_validation.py:18` — `TestConfig`, `compare_metric_family`, `load_metric_observation_bundle` | `consumer-up` | A composition CLI handler invokes Scientist validation; move the entry-point handler above Core. |
| CO-02 | `core/components/_cli_scientist.py:284` — `run_gonka_provider_smoke` | `consumer-up` | Scientist provider evaluation is composition behavior, not Core infrastructure. |
| CO-03 | `core/components/_cli_scientist.py:317` — `run_starter_eval_harness` | `consumer-up` | The evaluation harness consumer belongs in an upper CLI composition owner. |
| CO-04 | `core/components/_cli_scientist.py:345` — `evaluate_reflexion_replay_cases` | `consumer-up` | Reflexion evaluation is Scientist behavior; relocate the command handler rather than hide the import. |
| FS-01 | `foundry/validation/release_acceptance.py:33` — `postflight_checks` | `consumer-up` | Scientist owns governance admission; make it the real content-bound D5 consumer and leave Foundry execution below. |
| FS-02 | `foundry/calibration/calibrator.py:559` — `apply_calibration_meta_overrides` | `consumer-up` | Scientist owns calibration meta-policy; execute the override in Scientist around neutral Foundry calibration inputs/results. |
| FS-03 | `foundry/calibration/dp_ci.py:179` — `JudgeThresholdRegistry` | `consumer-up` | Threshold governance belongs in Scientist; Foundry computes intervals and passes their neutral evidence upward. |
| FS-04 | `foundry/methods/catalog/causal/composition_failure_cards.py:20` — `FailureSeverity`, `TypedFailureCard` | `shared-contract-down` | These dependency-free failure DTOs cross Foundry and Scientist; consolidate them in the existing neutral IR analytics contract. |
| FS-05 | `foundry/methods/catalog/policy/frontier.py:23` — `SentenceTransformerEmbedder`, `TFIDFEmbedder` | `shared-contract-down` | The generic implementations are consumed in both roots and carry no Scientist authority; lower their single implementation to Foundry. |
| IF-01 | `ir/observation/contract_compilers.py:20` — `DynamicTreatmentData`, `NetworkCausalData`, `PanelObservationalData`, `ProxyMeasurementData` | `consumer-up` | IR owns manifests/codecs; Foundry data-plane owns concrete method DTO materialization. |
| IF-02 | `ir/observation/contract_compilers.py:26` — `PanelData` | `consumer-up` | Constructing an econometric protocol input is Foundry binding behavior; retain the neutral panel manifest in IR. |
| IF-03 | `ir/observation/contract_compilers.py:27` — `SurveyMicroData` | `consumer-up` | Survey-to-method materialization belongs with Foundry microsimulation. |
| IF-04 | `ir/observation/contract_compilers.py:28` — `SurvivalData` | `consumer-up` | Censoring rows remain neutral IR data; the ML protocol constructor moves upward. |
| IF-05 | `ir/observation/contract_compilers.py:29` — `MultiplexNetworkData`, `NetworkData` | `consumer-up` | IR keeps graph payloads/manifests; Foundry binds concrete network method contracts. |
| IF-06 | `ir/observation/causal_execution.py:39` — `DynamicTreatmentData` (`TYPE_CHECKING`) | `consumer-up` | A neutral task must not expose a concrete Foundry DTO; validate/materialize its payload at the upper adapter. |
| IF-07 | `ir/observation/causal_execution.py:51` — `DynamicTreatmentData` (runtime) | `consumer-up` | This independent Pydantic/runtime import is the second half of the same upper materialization seam. |
| IF-08 | `ir/analytics/strategic.py:2232` — `strategic_decomposition_summary` | `consumer-up` | IR persistence interprets a Foundry solve result; interpretation moves beside the Foundry producer. |
| IF-09 | `ir/analytics/strategic.py:2274` — `build_strategic_response_bundle`, `strategic_decomposition_summary` | `consumer-up` | Foundry owns solve-result-to-response assembly; IR retains dependency-neutral persistence helpers. |
| IF-10 | `ir/analytics/transportability.py:343` — `SourceDomain` | `consumer-up` | Neutral `SourceDomainSpec` stays in IR; conversion to the Foundry ID-engine DTO moves beside that engine. |
| IF-11 | `ir/passes/core.py:395` — `classify_estimand` | `consumer-up` | Execution-aware estimand classification belongs in the existing Foundry compiler, not an IR pass. |
| IF-12 | `ir/passes/core.py:396` — `build_kernel_estimator_spec`, `should_request_kernel_lowering` | `consumer-up` | Kernel strategy selection/construction is Foundry behavior; consolidate the duplicate IR lowering path. |
| IF-13 | `ir/observation/compiler.py:20` — `MEASUREMENT_AWARE_TARGET_CONTRACT`, `CalibrationTargetBundle`, `MeasurementAwareTarget` | `consumer-up` | The compiler materializes Foundry calibration objects; move compiler/placebo bundle work to the existing Foundry measurement owner. |
| IS-01 | `ir/observation/bundles.py:32` — `HistoricalValidationPlan` (`TYPE_CHECKING`) | `consumer-up` | IR transports neutral payloads; Scientist owns executable backtest plans. |
| IS-02 | `ir/observation/bundles.py:41` — `HistoricalValidationPlan` (runtime) | `consumer-up` | The independent runtime/Pydantic half must move to Scientist intake with malformed-payload rejection. |
| IS-03 | `ir/observation/contract_compilers.py:82` — `HistoricalValidationPlan`, `PredictionSource` | `consumer-up` | Defaulting and materializing executable validation plans is Scientist backtesting behavior. |
| IS-04 | `ir/analytics/alignment_certification.py:46` — `build_fragment_alignment_ontology_warnings` | `consumer-up` | Scientist computes ontology-service warnings and injects a frozen typed snapshot into pure IR certificate building. |
| IS-05 | `ir/analytics/alignment_certification.py:49` — `assess_latent_bridge_governance`, `materialize_latent_bridge_governance` | `consumer-up` | Promotion/readiness governance remains Scientist-owned; IR persists supplied neutral outcomes. |
| IS-06 | `ir/analytics/strategic.py:28` — `ComputeBudget` | `shared-contract-down` | This dependency-free schema is embedded in IR and shared broadly; lower one identity to existing IR and re-export it from Scientist. |
| IC-01 | `ir/analytics/phase4_dynamics.py:13` — `ExecPlanRef`, `IdentifiabilityDiagnosticRef`, `MetricsRef`, `SimulationResult` | `consumer-up` | IR owns an analytical result, while Core execution refs/results are converted at the existing Foundry simulation boundary. |
| IC-02 | `ir/analytics/simulation_proof_bridge.py:12` — `TruthfulnessReceipt`, `TruthfulnessScope`, `TruthfulnessTier`, `extract_truthfulness_receipt`, `truthfulness_depth`, `validate_truthfulness_receipt` | `shared-contract-down` | Consolidate the duplicate identity/helper set in existing IR truthfulness ownership; Core re-exports it and the bridge stays in IR. |
| IJ-01 | `ir/observation/compiler.py:15` — `jax.numpy as jnp` | `consumer-up` | Every tensor use serves the adjacent Foundry calibration compiler; move JAX/NumPy materialization with that compiler and close this row separately. |

## Widening ledger

| Commit boundary | Ledger | What it bought / rows cleared | Standing |
| --- | ---: | --- | --- |
| pinned base / pre-edit census | 0/10 | No mechanism change; all 39 statements classified, 0 ambiguous. | stands; no round consumed |
| seam 1 — Lex/Foundry intervention coupling | 0/10 | Existing IR now owns `CompiledLexIntervention`; existing Scientist nodes own hierarchical-search and temporal-DTR execution. Cleared `lex -> foundry` 3/3, `lex -> scientist` 4/4, and `foundry -> lex` 1/1. | stands; downward shared-contract completion and consumer-up relocation are round-free |

No round has been withdrawn.

## Pattern and capability pass

Relevant patterns before design: P01/P02/P12, P05/P15/P32/P37,
P06/P27/P31, P29/P33/P38, P35/P36, P39/P40/P41. The target pattern is one
canonical lower identity for shared contracts and an explicit upper consumer
for behavior/authority. The release-acceptance D5 seam begins
`bridge_missing` / `consumer_missing`; it cannot be called complete until a
Scientist consumer verifies and persists the handoff. Other capability states
will be recorded at their seam boundaries rather than inferred from contracts.

## Collision dispositions

- `simulation_proof_bridge`: stays in IR. Truthfulness models and helpers move
  to the existing IR canonical implementation; Core becomes an identity
  re-export. This closes only the shared statement and does not claim the wider
  observability family.
- `observation/compiler.py`: calibration/JAX code moves as one physical seam,
  but `IF-13` and `IJ-01` remain separately enumerated and separately closed.

## Execution receipts

### Seam 1 — Lex/Foundry intervention coupling

- Attachment before closeout: prefix `policy-engine/`, branch
  `refs/heads/codex/import-relocations-nine-seams`, attached at the pinned-base
  descendant.
- Mechanism path set (20 observed = 20 declared): IR contract/facades (3), Lex
  contract/docs (4), existing Scientist planning/causal consumers (4), Foundry
  wiring (1), focused tests (5), Lex reference docs (2), and the structured
  release fragment (1). The spec, plan, and this journal are the three mandatory
  P39 record companions and are outside the mechanism count.
- TDD RED was the missing IR export during relocation (collection exit 2). The
  pre-source characterization also established the existing explicit-bounds
  failure in
  `test_hierarchical_policy_search_adapter_validates_against_policy_design_api`;
  its message is `Lex search bounds are missing or invalid; no default zero may
  be used.` The base environment's missing `sklearn` was a tooling non-receipt,
  so the focused wave used a temporary `uv --with scikit-learn` overlay.
- Initial seven-file focused wave: direct exit 1, 39 passed and the one
  previously established bounds-gate test failed. After delta-review fixes,
  the final wave with only that inherited test deselected completed direct exit
  0 with 41 passed; `real=30.90s`, `user=32.05s`, `sys=1.69s`, uptime
  21:26/up 3d11:39 at both endpoints.
- Changed-file Ruff: direct exit 0. Restricted `git diff --check`: direct exit
  0. The release fragment parses as TOML.
- The Lex root-surface count is 51 by both complete AST evaluation of `__all__`
  and runtime `len(polisyos.lex.__all__)`; runtime uniqueness is also 51 and the
  reference-table groups sum to 51.
- The three row-owned literal commands each completed direct exit 0:
  `lex -> foundry`, `lex -> scientist`, and `foundry -> lex`.
- Deferred enumerated deep-edge additions are the existing Scientist causal
  node to Foundry `causal_engine`, `dtr`, and `protocols` modules. They are not
  synchronized into the baseline by a generator.
- Capability result: the contract has one neutral IR identity; Lex remains the
  producer of compiled legal inputs; Scientist is the execution bridge and
  consumer; Foundry supplies causal execution. The three removed Lex execution
  helpers have an explicit breaking migration fragment rather than upward
  shims. No ambiguous statement remains.
- Delta review found and closed four relocation regressions before commit:
  `compiled_interventions=None` again coerces to the empty list; the existing
  `PolicySearchLevel` enum identity is lowered to IR and re-exported by
  Scientist rather than replaced with strings; moved adapters are excluded
  from node-module `__all__`; and removal of the public
  `to_dynamic_treatment` method is now explicit in both migration docs and the
  release fragment. A final negative probe also proves that neither old Lex
  module path silently re-exports `CompiledLexIntervention`.
