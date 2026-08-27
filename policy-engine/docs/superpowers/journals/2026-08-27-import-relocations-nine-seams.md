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
| seam 2 — Core metric-validation CLI | 1/10 | One new packaged tools composition module owns the installed CLI and metric-validation handler. Cleared CO-01, the first 1/4 `core -> scientist` statements; the row remains open on CO-02..04. | stands; round 1 bought `tools/ops_runners/runtime_cli.py` |
| seam 3 — Core Scientist CLI | 1/10 | The already-paid tools composition module now owns all nine Scientist commands; Core's remaining three upper-runtime imports and its obsolete internal handler are gone. Cleared CO-02..04 and closed `core -> scientist` 4/4. | stands; no new module, package, public authority export, constraint loosening, or surface |
| seam 4 — D5 release acceptance | 2/10 | A strict D5 handoff/admission/technical-receipt/Scientist-decision chain replaces Foundry's direct governance call. Cleared FS-01, the release-acceptance member of `foundry -> scientist`; the composite working tree also closes the row after the separately declared pending seams remove FS-02..05. | stands; round 2 bought the new typed D5 admission and release-decision surface, with purpose-limited authority and fail-closed predicate provenance |
| seam 5 — calibration policy pair | 3/10 | Scientist now applies calibration meta-overrides before persisting Foundry inputs and resolves the complete CI-threshold scope before dispatch; Foundry consumes only a typed resolved policy set or declared local defaults. Cleared FS-02 and FS-03. | stands; round 3 bought the public-stable `CITestThresholdPolicySet` handoff and its explicit breaking migration surface |
| seam 6 — composition failure-card contract | 4/10 | The dependency-neutral failure-card DTOs/enums have one IR identity consumed by the existing Foundry producer and Scientist persistence/orchestration paths. Cleared FS-04. | stands; round 4 bought the three-name stable IR contract surface and its schema/identity obligations; shared generated inventory projection is deferred intact to the final generator boundary |
| seam 7 — policy-frontier embedders | 5/10 | Generic TF-IDF and optional sentence-transformer implementations now have one Foundry-owned identity; existing Foundry and Scientist consumers use the narrow stable root. Cleared FS-05 and closes `foundry -> scientist` 5/5. | stands; round 5 bought exactly three stable root names; the rejected 26-name backend publication was withdrawn and consumed no additional round |
| seam 8 — IR method-protocol binding | 6/10 | IR now emits neutral JSON payloads for nine method-contract families; one fail-closed Foundry materializer admits them by exact contract ID and FQN, and both real upper consumers use that chokepoint. Cleared IF-01..07. | stands; round 6 bought the single new `foundry.data_plane.materialize_method_contract` export; the P31 consumer repair widened the same mechanism and consumed no additional round |
| seam 9 — IR strategic/transportability adapters | 6/10 | Existing Foundry owners now interpret solve results, assemble strategic responses, and materialize `SourceDomain`; IR retains neutral declarations and persistence only. Cleared IF-08..10. | stands; consumer-up relocation into existing modules and already-allowed directions introduced no package, module, surface, authority publication, or constraint loosening |
| seam 10 — IR kernel lowering | 6/10 | The duplicate execution-aware IR pass is removed; the existing Foundry compiler now carries a typed blocked kernel specification through real refusal execution and audit persistence. Cleared IF-11/12. | stands; consolidation and a private repair inside existing Foundry ownership introduced no new surface or constraint |

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
- Observed seam path set (20 observed = 20 declared): 11 source mechanism
  paths plus 9 P39 companions (5 focused tests, 3 Lex/reference docs, and the
  structured release fragment). The spec, plan, and this journal are three
  additional global record companions outside the mechanism count.
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

### Seam 2 — Core metric-validation CLI

- Attachment/prefix at closeout: `policy-engine/` on attached
  `refs/heads/codex/import-relocations-nine-seams`, with Seam 1 commit
  `6a12c05ea` read back before this work was staged.
- Observed seam path set (16 observed = 16 declared): 5 mechanism paths (the
  new tools composition module, three deleted Core CLI modules, and the console
  entry-point declaration) plus 11 P39 companions (dynamic/exception/Ruff
  registries, CLI documentation, and six focused test paths). This journal and
  the implementation plan are two additional record companions.
- TDD RED: the installed-entrypoint ownership assertion failed against the old
  Core target (direct exit 1). The plain metric characterization was a tooling
  non-receipt because the default environment lacked `sklearn`; the declared
  ML-extra run was the accepted receipt.
- Final six-file CLI/importer wave under `--extra ml`: direct exit 0, 33 passed;
  `real=37.27s`, `user=34.97s`, `sys=1.98s`, uptime 21:32/up 3d11:45 to
  21:32/up 3d11:46. Changed-file Ruff and installed `polisyos --version`
  each completed direct exit 0; the latter printed `polisyos 0.1.0`.
- Complete AST traversal over all 205 Core Python files found three remaining
  Core-to-Scientist statements, exactly CO-02..04 in `_cli_scientist.py`, and
  zero imports of `scientist.validation.metrics`. A complete-tree `rg`
  independently found zero metric imports. The row's own literal command
  therefore correctly remains direct exit 1; the canonical linter independently
  counts three remaining findings. No row closure is claimed at this boundary.
- The dynamic-import collector and registry independently enumerate the same
  two `runtime_cli.py` calls (lines 31 and 470). The exception TOML and its
  Markdown projection independently count 22 rows after removing the obsolete
  metric exception.
- Review re-derived an unchanged parser AST and all 26 unaffected dispatch
  mappings, confirmed the wheel includes the tools module, and found no
  supported consumer of the deleted internal Core module. No finding remained.
- Capability result: the stable console script is the surface; the upper tools
  composition root is its real bridge/consumer and directly invokes the
  existing typed metric producer/persistence path. The new module mints no
  policy authority, but is a new surface and therefore consumes round 1.

### Seam 3 — Core Scientist CLI

- Attachment/prefix before closeout: `policy-engine/` on attached
  `refs/heads/codex/import-relocations-nine-seams`, with Seam 2 commit
  `47b5f1bfd` read back before staging.
- Observed seam path set (8 observed = 8 declared): 2 mechanism paths (the
  existing tools composition module and deleted Core handler) plus 6 P39
  companions (dynamic registry, TOML/Markdown exception projections, Core
  component README, and two focused test paths). This journal and the
  implementation plan are two additional mandatory record companions outside
  the mechanism count.
- The move is structurally exact: AST-normalized comparison found all 14
  definitions from the deleted handler present and unchanged in the tools
  composition module. Dispatch now calls those local handlers directly; the
  installed `polisyos scientist --help` smoke completed direct exit 0 and
  enumerated all nine commands.
- Final seven-file CLI/importer wave: direct exit 0, 51 passed;
  `real=29.11s`, `user=26.83s`, `sys=1.25s`, uptime 21:53/up 3d12:07 to
  21:54/up 3d12:07. Changed-file Ruff and unrestricted `git diff --check`
  each completed direct exit 0.
- A complete AST traversal and an independent `rg --files` derivation each
  enumerated 204 Core Python files. The AST import walk and an independent
  complete-tree text scan each found zero Core-to-Scientist imports. The row's
  literal closure command completed direct exit 0.
- The runtime collector and registry each enumerate exactly 20 tools CLI
  dynamic calls: missing=0, stale=0, and obsolete `_cli_scientist.py` rows=0.
  The exception TOML and its Markdown projection independently enumerate the
  same 21 IDs after removal of the closed Core exception.
- Capability result: the supported console script remains unchanged; its
  already-existing upper composition owner is the bridge and real consumer of
  Scientist provider, agent-evaluation, reflexion, search, and backtesting
  behavior. Core now supplies only lower CLI parser/store infrastructure. No
  facade, compatibility shim, new authority, or widening round was introduced.
- Independent delta review found no behavioral or architectural defect. Its
  sole minor finding was a stale prose denominator (`22`) in the exception
  projection; that P35 mismatch was corrected to the independently verified
  TOML/Markdown count of 21 before commit.

### Seam 4 — D5 release acceptance

- Attachment/prefix before staging: `policy-engine/` on attached
  `refs/heads/codex/import-relocations-nine-seams`, with Seam 3 commit
  `d5bb48724` read back before the seam was staged.
- Observed seam path set (14 observed = 14 declared): 8 mechanism/configuration
  paths (`pyproject.toml`, three DataForge producer/admission paths, two Foundry
  technical-execution paths, one Scientist governance consumer, and the tools
  composition root) plus 6 focused-test companions. This journal and the
  implementation plan are two additional P39 record companions.
- DataForge now emits a purpose-limited handoff whose exact manifest/evidence
  set is admitted by path, hash, byte size, and CAS content. Foundry compiles,
  executes, and replays only CAS-admitted inputs and emits a frozen technical
  receipt with no release/legal authority. Scientist independently reconciles
  compression evidence, reloads and exact-binds the persisted D4 receipt,
  evaluates postflight checks, and emits the strict release-decision packet.
- The gate predicates are frozen at admission as follows: artifact content and
  hashes are recomputed; compression aggregates are
  `independently_reconciled`; D4 is `independently_reconciled` only after the
  persisted Scientist bundle and producer receipt exact-bind, otherwise
  `not_established`; a missing/inconsistent predicate fails closed. Manifest
  error findings, forged bytes, path escape, non-exact evidence, self-consistent
  handoff mismatch, inadequate compression, missing D4, and postflight failure
  each have a negative semantic test.
- The first root 26-test receipt was rejected as a harness receipt: pytest
  printed 26 passes, then zsh rejected the wrapper's read-only variable name
  `status`, so the wrapper exited 1 after the product run. The corrected final
  command completed direct exit 0 with 26 passed; `real=80.93s`,
  `user=68.62s`, `sys=5.97s`, uptime 23:20/up 3d13:33 to
  23:21/up 3d13:34. Changed-path Ruff and restricted `git diff --check` each
  completed direct exit 0.
- A complete AST traversal over all 600 Foundry Python files found zero imports
  of `polisyos.scientist`. The earlier broader assertion "zero DataForge or
  Scientist imports" was rejected: the same complete traversal found two
  pre-existing DataForge imports outside this seam. The row-owned literal
  command completed direct exit 0 on the composite tree; this seam claims only
  FS-01 because the still-uncommitted, separately declared calibration,
  failure-card, and embedder seams supply the removals of FS-02..05.
- Capability result: DataForge is the typed producer and content-bound
  admission owner; Foundry is the technical producer; Scientist is the real
  governance bridge/consumer; CAS artifacts and the decision packet are the
  persisted/audit-visible surface. The initial `consumer_missing` /
  `bridge_missing` state is closed without laundering Foundry's technical pass
  into publication or legal authority.
- Independent review initially returned NO-GO for ignored manifest errors,
  declared-only D4/compression predicates, ambiguous authority, compatibility
  regressions, and missing negative cases. After one batched P40 repair, the
  delta review returned Ready with no remaining Critical/Important/Minor
  finding; its 15 falsifier/integration tests passed.

### Seam 5 — calibration policy pair

- Attachment/prefix before staging: `policy-engine/` on attached
  `refs/heads/codex/import-relocations-nine-seams`, with Seam 4 commit
  `cd14d2da1` read back before staging.
- Observed seam path set (21 observed = 21 declared): 10 source mechanism
  paths (three Foundry calibration paths, three real causal-method consumers,
  one IR schema correction, and three Scientist policy/orchestration paths)
  plus 11 P39 companions (10 focused-test paths and one additive release
  fragment). This journal and the implementation plan are two additional
  record companions.
- FS-02 now applies Scientist's existing meta-policy before the exact
  `CalibrationConfig` is persisted and passed to `Calibrator`; Foundry no
  longer reaches upward during execution. FS-03 uses the existing Scientist
  threshold registry to produce a frozen `CITestThresholdPolicySet`; real
  Foundry PC/FCI/PCMCI, kernel-CI, and missingness routes receive only the
  resolved payload or their declared local defaults.
- All seven scope discriminators — family, query type, estimator, readiness
  target, DP mechanism, epsilon bucket, and delta bucket — are recomputed from
  the runtime call and exact-matched before dispatch. A family, privacy-bucket,
  duplicate, missing, or otherwise mismatched policy fails before Foundry
  execution; no path/self-attestation controls the technical decision.
- One initial root test selection was rejected as a harness non-receipt: two
  correct test names were assigned to the wrong files, so collection completed
  exit 4 (`real=257.20s` under unrelated CPU contention). Resolving the names
  over the complete `tests/` tree and running the six selected real-path,
  persistence, registry, dispatch, and mismatch tests completed direct exit 0
  with 6 passed; `real=52.01s`, `user=46.10s`, `sys=2.95s`, uptime
  23:39/up 3d13:52 to 23:40/up 3d13:53.
- Changed-path Ruff, restricted `git diff --check`, release-fragment TOML
  parsing, and the two exact calibration-module AST checks each completed
  direct exit 0. The schema round-trip test exposed and closes the pre-existing
  escaped-regex defect that rejected the persisted default version `0.1`.
- A complete AST traversal over all 600 Foundry Python files found zero
  Scientist imports. The row-owned literal command independently completed
  direct exit 0 on the composite tree. This seam claims FS-02/03; FS-01 was
  committed separately and FS-04/05 remain separately declared dirty seams.
- Capability result: the existing registry/meta-policy producers, typed policy
  artifact, persistence/dispatch bridges, real Foundry consumers, compatibility
  surface, and negative semantic tests are wired. The prior upper-authority
  leak is closed; direct callers receive the documented TypeError or compiled
  parameter-validation failure rather than a compatibility callback into
  Scientist.
- Independent review found three rollout/compatibility issues in its first
  pass; the batched repair added the stable facade identity, exact direct versus
  compiled exception contract, and real persisted/dispatch coverage. Final
  delta review returned Ready with no remaining finding.

### Seam 6 — composition failure-card contract

- Attachment/prefix before staging: `policy-engine/` on attached
  `refs/heads/codex/import-relocations-nine-seams`, with Seam 5 commit
  `9a46a1e10` read back before staging.
- Observed seam path set is 27 declared commit paths: 15 source mechanism
  paths, the IR facade, 7 focused-test paths, 2 recomputing semantic validators,
  and this plan/journal pair. The two shared generated public-inventory paths
  are deliberately not split by hunk or attributed to this commit: their
  current generator-complete delta jointly projects Seams 1, 6, and 7 and is
  retained for the final sync/baseline boundary.
- `FailureSeverity`, `TypedFailureCard`, and `UncertaintyType` now have one
  dependency-neutral implementation in existing IR analytics and exact root
  facade identities. Foundry emits the typed cards; Scientist challenge,
  funnel, judge, memory, critic, and preflight consumers import that identity.
  The old Scientist owner and test are deleted without a facade shim.
- Persisted bundles use the existing artifact path with schema
  `ir.composition_failure_card_bundle@1.0`; explicit conversions preserve upper
  `ArtifactRef` consumers. Producer-to-persistence-to-Scientist consumption is
  covered, including severity/uncertainty semantics and malformed/legacy-path
  negatives rather than constructor-only checks.
- Root's seven-file focused wave completed direct exit 0 with 48 passed;
  `real=86.80s`, `user=69.33s`, `sys=4.85s`, uptime 23:42/up 3d13:55 to
  23:44/up 3d13:57. The independently executed wider seam wave completed with
  70 passes before review.
- Both recomputing validators (`scientist-best-in-class-phase2-5` and Wave 2)
  completed direct exit 0 and reported accepted. Changed-path Ruff and
  restricted `git diff --check` completed direct exit 0.
- Complete `rg --files -g '*.py'` enumeration found 5,665 repository Python
  paths; its AST import walk found zero imports of the deleted Scientist module,
  and an independent complete-tree text scan also found zero (expected `rg`
  exit 1). Runtime identity initially imported the main checkout through the
  ambient editable install and was rejected as a tooling non-receipt; the
  explicit worktree `PYTHONPATH=src` probe completed exit 0 with all three
  identities exact.
- Capability result: typed contract, real Foundry producer, persisted bundle,
  Scientist bridge/consumers, recomputing validators, root facade, and negative
  semantic tests are wired. Independent review twice returned Ready after the
  facade identity and generic consumer coverage were added. No ambiguous
  statement remains.

### Seam 7 — policy-frontier embedders

- Attachment/prefix before staging: `policy-engine/` on attached
  `refs/heads/codex/import-relocations-nine-seams`, with Seam 6 commit
  `558789ad5` read back before staging.
- Observed commit path set is 19 declared paths: the exact 17-path FS-05
  mechanism/contract/documentation/test set plus this plan/journal pair. The
  lazy backend facade is part of the mechanism; the shared generated inventory
  and reference projection remain unstaged for the final serialized generator
  boundary; they currently combine Seams 1, 6, and 7.
- The canonical implementation moved from the deleted Scientist owner to the
  existing Foundry backend protocol module. The already-stable lazy
  `polisyos.foundry` root publishes exactly `EmbedderProtocol`,
  `TFIDFEmbedder`, and `SentenceTransformerEmbedder`; all consumers use those
  identities. The optional sentence-transformers dependency remains lazy and
  fails with the preserved install guidance, and TF-IDF output matches the
  legacy oracle.
- The first implementation attempt declared the whole
  `polisyos.foundry.methods.backends` facade stable, unintentionally graduating
  23 unrelated internals alongside the three names. Independent review returned
  Not Ready and demonstrated why that obligation was material with an existing
  async-executor defect. The attempt was withdrawn. The first narrow-root
  repair still initialized the eager backend package and cached a partial
  `AsyncChainExecutor=None`; P40 classified this as the same import-state class,
  so the mechanism was widened once to make the existing 23-name backend facade
  genuinely lazy. Its names and identities are unchanged, its overlap with the
  embedder set is zero, and the stable root remains the only new surface. No
  second widening round is charged.
- Root's four-file surface/behavior wave completed direct exit 0 with 48 passed
  and one expected BoTorch-not-installed skip; `real=38.28s`, `user=32.13s`,
  `sys=2.37s`, uptime 00:01/up 3d14:14 to 00:02/up 3d14:15. The implementer
  independently completed the final repaired 52-test wave and strict mypy over
  all five touched source modules. Root then ran the three decisive
  surface/lazy-executor falsifiers against the final repair: direct exit 0,
  3 passed, `real=33.92s`, `user=32.45s`, `sys=1.34s`, uptime 00:27 at both
  endpoints.
- A first static wrapper passed TOML/INI/Markdown paths to Ruff and was rejected
  as a harness non-receipt after emitting syntax noise. The corrected Python-only
  Ruff command, restricted `git diff --check`, both TOML parses, and the live
  identity/surface falsifier completed direct exit 0: Foundry root total=11,
  embedder additions=3, backend internal total=23, overlap=0, and an unrelated
  backend function is absent from the root. The behavioral subprocess proves
  that resolving the real frontier/root embedder leaves chain modules unloaded,
  then lazily resolves `AsyncChainExecutor` and awaits a compatible empty chain.
- Complete AST traversal over the 2,594 `src/**/*.py` files found zero imports
  of the retired Scientist owner; the implementer's independent broader
  5,474-file denominator also found zero. The row-owned literal command
  completed direct exit 0 and `foundry -> scientist` is closed 5/5.
- Capability result: canonical owner, typed protocol/implementations, real
  Foundry producer/consumer and Scientist consumer, public compatibility
  surface, optional-dependency negative test, identity tests, and migration
  fragment are present. The surface carries no policy authority; its one round
  is charged solely because the three-name stable API is new.
- The subsequent `FrozenCompositionDAG.compute_parallel_levels` mismatch was
  bucketed as a bounded, pre-existing async-DAG contract gap: an isolated clean
  HEAD replay reproduces it without any embedder import, while
  `chain_executor.py` is byte-identical to HEAD in this patch. The smallest
  future closure is a persisted immutable effective dependency/parallel-level
  plan across compilation and executors; that capability is outside this seam.
  Final independent delta review returned Ready after the lazy-facade repair.

### Seam 8 — IR method-protocol binding

- Attachment/prefix before staging: `policy-engine/` on attached
  `refs/heads/codex/import-relocations-nine-seams`, with Seam 7 commit
  `85f0b8f935ec` read back before staging.
- Observed mechanism/test path set is exactly 10 paths: two existing Foundry
  data-plane paths, two IR observation paths, two Scientist consumer paths,
  and four focused test paths. This plan and journal are the two mandatory P39
  record companions. The dirty C7 integration test belongs to Seam 11 and is
  deliberately excluded from this commit.
- IR emits deterministic JSON payloads for all nine causal, econometric,
  microsimulation, ML, and network families. The existing Foundry data-plane
  owns a single allow-registry/materializer that exact-matches both stable
  contract ID and fully qualified name before strict DTO validation. Unknown
  IDs, mismatched FQNs, and malformed known payloads fail closed.
- The P31 reopen found the C7 survival adapter's direct `.features` assumption.
  A complete 2,594/2,594-file production AST census, independently matched by
  `rg --files`, found three materializer call sites: the central Foundry intake
  and the two real neutral-payload consumers (DTR and C7 survival). Both real
  consumers now use the same chokepoint; the apparent simulation route reloads
  CAS data already admitted at Foundry intake. Six unused family outputs remain
  `consumer_missing` if claimed individually; proxy is bundle-consumed. No
  residual sibling consumer or ambiguous statement remains.
- The P31 repair was demonstrated RED at the original dict `.features` escape
  (2 failed; `real=44.40s`, `user=42.19s`, `sys=1.64s`) and GREEN after the
  chokepoint repair (2 passed; `real=40.56s`, `user=38.99s`, `sys=1.41s`).
  Independent review ran six decisive materialization/consumer tests in
  37.09s and returned Ready. Root separately reran the previously failing real
  C7 synthetic pipeline: direct exit 0, 1 passed, `real=53.64s`,
  `user=53.66s`, `sys=3.08s`, with uptime 00:38/up 3d14:52 to
  00:39/up 3d14:52. Changed-path Ruff, compile checks, and `git diff --check`
  completed exit 0.
- Independent two-file AST comparison reports the seven IR-to-Foundry
  statements moved 7 -> 0 without a facade. The complete current source
  linter reports 11 findings total and zero `ir -> foundry`; the row's exact
  literal closure command completed direct exit 0. This seam claims IF-01..07;
  the separately declared strategic, lowering, and compiler/JAX seams supply
  the other six removals already present in the composite tree.
- Capability result: neutral typed target/payload contract, IR producer,
  persisted bundle/CAS routes, Foundry admission bridge, two real Scientist
  consumers, strict negative verification, and internal audit-visible payloads
  are wired. Materialization grants no policy authority. Round 6 is charged
  solely for the new `foundry.data_plane` export; the same-class P31 repair
  widened that one mechanism and consumed no second round.

### Seam 9 — IR strategic/transportability adapters

- Attachment/prefix before staging: `policy-engine/` on attached
  `refs/heads/codex/import-relocations-nine-seams`, with Seam 8 commit
  `752b27e07553` read back after writing and before this boundary.
- Observed seam path set is exactly 11 paths: four Foundry/IR mechanism paths,
  three existing Scientist consumers, and four focused test paths. This plan
  and journal are the two P39 record companions. No shared generated path is
  attributed to the seam.
- The existing Foundry strategic owner now interprets Foundry solver results
  and builds the response bundle. IR retains dependency-neutral strategic
  declarations and persistence. The existing Foundry ID-engine transport owner
  converts strict `SourceDomainSpec` values to `SourceDomain`; mapping-shaped
  stand-ins are rejected rather than silently admitted.
- The focused implementation wave passed 3 tests. Independent review then ran
  the 34-test strategic/transport blast radius plus two transportability
  falsifiers; both receipts passed. Changed-path Ruff and `git diff --check`
  completed direct exit 0. Full-file Ruff still reports pre-existing F821/I001
  findings in touched large files, so the scoped unchanged-code comparison used
  the recorded `--ignore F821,I001` baseline and was green; because the touched
  files intersect the gate denominator, provenance of those full-file reds is
  `not_established` under P41 rather than claimed inherited.
- Complete AST enumeration removes IF-08..10. The composite source linter and
  the row's literal command report zero `ir -> foundry`; this seam claims the
  three strategic/transport removals only, separately from the protocol,
  lowering, and compiler/JAX seams.
- Capability result: Foundry remains the technical producer and conversion
  owner, IR carries neutral typed inputs/persisted artifacts, and the existing
  Scientist nodes are the real orchestration consumers. Strict type rejection
  and end-to-end strategic-response coverage supply the semantic negatives.
  This downward/consumer-up move uses existing modules and surfaces and consumes
  no widening round; the ledger remains 6/10.

### Seam 10 — IR kernel lowering

- Attachment/prefix before staging: `policy-engine/` on attached
  `refs/heads/codex/import-relocations-nine-seams`, with Seam 9 commit
  `c3ad78f933aa` read back after writing and before this boundary.
- Observed mechanism/test path set is exactly four: the existing Foundry
  estimand compiler, the IR pass implementation and facade, and the focused
  Foundry kernel runtime test. This plan/journal pair are P39 record companions.
  `docs/reference/ir/schema-catalog.md` is a mandatory generated companion that
  still names the deleted pass and is explicitly deferred to the final
  serialized generator boundary; its current `--check` correctly reports stale.
- The duplicate, unwired `KernelLoweringPass` is removed from IR and its facade;
  existing Foundry lowering remains canonical. Review exposed a NEW class inside
  the same seam: the first test checked a recommendation marker, while the real
  `KernelRefusal` could not execute because compilation omitted `kernel_spec`.
  This was bucketed as `semantic_test_missing` / P38, not another ownership
  relocation instance.
- The repair deterministically rebuilds the same typed blocked
  `KernelEstimatorSpec` at the existing Foundry compiler and binds its JSON to
  the kernel-refusal node. A RED real compile -> execute -> audit test observed
  `report is None` (`real=31.64s`, `user=29.56s`, `sys=1.38s`). GREEN reports
  `ASSUMPTION_FAILED`, exact `operator_certificate_missing`, CAS-persisted
  `proof_only` disposition, and audit method configuration (`real=33.27s`,
  `user=31.41s`, `sys=1.45s`). The 12-test focused lowering/runtime wave passed;
  independent review reran four kernel tests and returned Ready.
- The refusal parameter is gated only on `causal.kernel.refusal@1.0.0`; the
  existing generic recovery-refusal test remains green. Complete independent
  AST census over 5,044 source/test Python files found zero live
  `KernelLoweringPass` references and zero IR-to-Foundry imports. Changed-path
  Ruff and `git diff --check` completed exit 0.
- Capability result: the existing Foundry compiler produces the typed blocked
  spec, the executable DAG carries it, the engine consumes it, CAS/audit persist
  it, and the negative semantic test proves the refused path itself works.
  Consolidation uses existing owners and surfaces, so the ledger remains 6/10.
