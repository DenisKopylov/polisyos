# N5 persisted-result / conditional N8 intake

This handoff records a bounded candidate witness on `codex/e02-A-n5-verify-current` at `7ffbf5c71d6352f7712673a6591be5e553993745` (tree `221f31490189a5a2865f1ce2e4b335d6342d6bd6`). The worktree was clean for the deciding run. The slice base is `198076863e143dea9f89f02734b13d50dae3eed5`. The structured receipt is the sibling `n5-intake.json`; this directory holds the complete moderate deciding output, exact run metadata, retained nonpassing attempts, and the exact removal-probe scripts used.

## Result and boundary

The deciding positive is one fresh-process test, `tests/unit/remediation/test_cyc_02.py::test_n5_fresh_process_readback_binds_default_n8_to_cas_identity`. It runs the canonical N5 `JointSimulationPort` producer and the actual default `_DefaultSimulationBoundFoundryValuePort` consumer in distinct Python processes. N5 writes to a real `FileSystemCAS`; the reader reopens and verifies the artifact and sibling receipt digest. The test checks exactly one selected `EngineDecision`, equality of its engine/method/objective identity across receipt and trajectories, the expected WMR reference and content hash, the candidate atom and selected outcome, and the returned effect against the persisted trajectory.

The fixture is synthetic and deliberately bounded: candidate `candidate_cyc_n5_builder`, atom `income_subsidy`, outcome `firm_survival`, objective `objective://firm-survival`, one-step static horizon, selected engine `ncm_parallel_worlds`, method `causal.counterfactual.ncm_engine@1.0.0`. The legacy candidate exposes `atom` but has no `intervention_atoms`; N8 falls back to that atom. A candidate with `intervention_atoms=()` is separately rejected.

The successful CAS result reference is `sha256:f27a7443408ac3faea7117b763640741170524d45ed92fae7195db9b63b9eca4`. Its receipt/sibling payload hash is `sha256:a36ebe38286617c67ed828622338ab1a10efafbc1521233e3e1f19f69ce3b095`. The validated WMR is `world_model_record_95c5f721bf9715f1`, content hash `sha256:95c5f721bf9715f127dbbaf76053be1892aae4e415940602024e0db94baee715`. The six CAS hashes and sizes emitted by the run are in `positive/pytest-timing-and-cas.json`; CAS bytes and basetemp contents are intentionally not committed.

The N8 result is only `value_conditional`, `evaluation_mode=simulate_only`, `decision_grade=low`; the blocker `simulation_only_k_sim_not_world_evidence` remains, and both value and method-selection authority receipts are absent. This does not establish causal correctness, empirical effect, signer authorship, promotion or action authority. It is not a served HTTP route or N9 run, does not resolve an external profile/tenant/run/job authority chain, and does not test a production data profile. There is no N9 positive or refusal claim. The currentness receipt positive control required by B05 was not run.

## Criterion status

The authoritative A2 decision names B04, B05, B08 and B26 and keeps the closure status open. Its required full-manifest/profile, actual N9, served route, and higher-order consumer checks exceed this bounded witness.

- **B04 / CYC-02:** bounded positive readback shows persisted numerical content, receipt hash, WMR, atom/outcome, and selected engine identity survive a fresh consumer process. The test also makes valid-content variants for tampered CAS bytes, foreign WMR/atom/outcome, receipt/trajectory divergence, missing/zero/two selected engines, missing or mismatched sibling digest, and missing selected point distribution fail closed. This is evidence for part of B04, not finding closure: a production manifest/profile and other authorized consumer are absent.
- **B05 / CYC-02:** the test preserves K_sim as conditional simulation with its blocker. It never invokes N9; so it cannot show runtime-backed refusal or the required valid signed currentness-receipt positive control.
- **B08 / CYC-02:** a real default N8 conditional path and content-bound negatives are exercised. The fixture does not exercise an empirical effect route, and missing/zero/comparator/replication semantics remain outside this run.
- **B26 / SIM-03:** no higher-order interaction residual or typed N8 interaction-order/horizon/observed-steps behavior is tested. The three-atom multiplicative oracle remains open.

In `closure-decisions/coverage.json`, all four remain `closure_now=not_adjudicated`; B04/B05/B08 are `verification_missing`, while B26 is `surface_missing`. The separately reported Appendix-C statuses are not used to infer E02 closure. A2 itself also says causal correctness and signer authorship remain unverified. Exact criterion document hashes and line locators are in `n5-intake.json`.

## Behavioral removal controls

Each accepted removal control mutates the pinned runtime AST in memory, retains source markers, then runs the same producer-to-CAS-to-fresh-N8 test. The accepted witness is the exact target testcase's one semantic JUnit failure with the property-specific assertion, zero JUnit errors, and a confirmed mutation hit; the captured pytest failure is the expected observation under a removed property. The first three original harnesses printed a broad prefix marker; their PASS classification here comes from the retained target-specific JUnit assertion plus the harness's exact AST hit-count guard, not that broad marker. Later v3/v4 harnesses also recorded strict classifier fields in `result.json`.

The declared mutation denominator is the six property choices in the retained harness source. The portable `evidence_census.py` walks the complete committed removal-control directories, and `evidence-census.txt` records its output: nine per-run directories, nine `metadata.json` and nine `junit.xml` files, six accepted target-specific failures and three retained nonpasses. The census requires the exact target JUnit failure and property assertion; for earlier harness versions it also reads the versioned AST hit guard, and for v3/v4 it checks the strict result fields. The six accepted identities are:

| Property removed while markers remain | Actual N8 behavior under mutant | Exact semantic assertion in target JUnit |
| --- | --- | --- |
| selected-engine uniqueness, retaining the zero-selection guard | a duplicate selected engine reaches `value_conditional` | `removed_property_keep_markers:n8_negative_admitted:identity_multiple_selected_decisions` |
| sibling receipt-payload-hash comparison | foreign sibling digest reaches `value_conditional` | `removed_property_keep_markers:n8_negative_admitted:sibling_digest_mismatch` |
| explicit-empty atom rejection | present-empty candidate atoms reach `value_conditional` | `removed_property_keep_markers:n8_negative_admitted:explicit_empty_candidate_atoms` |
| selected outcome membership in each point's `outcomes` distribution | valid-CAS artifact missing the selected point outcome reaches `value_conditional` | `removed_property_keep_markers:n8_negative_admitted:missing_selected_point_outcome` |
| absent-atom fallback to the candidate's actual atom | ordinary no-`intervention_atoms` candidate becomes `value_blocked` | `removed_property_keep_markers:absent_atom_fallback_lost:` |
| CAS reference requirement before accepting a caller digest | CAS-less arbitrary digest becomes an `ArtifactRef` | `removed_property_keep_markers:casless_digest_admitted_before_fallback:` |

Each full metadata file, stdout/stderr, JUnit XML, exit code, and result record is under `removal-controls/<property>/`; the exact harness revisions are under `harness/`. In particular, the engine mutant changes `len(selected_decisions) != 1` to `len(selected_decisions) == 0`, so zero-selected fail-closed remains while uniqueness alone is removed.

Three early mutation attempts are preserved under `nonpassing/mutation-attempts/` and excluded from the six-control denominator: an overbroad engine-removal caused `selected_decisions[0]` IndexError rather than the semantic assertion; the first explicit-empty matcher missed the loader's `result.atom_ids` attribute and failed with `unexpected_mutation_hits=1`; the first CAS-less matcher targeted a Name instead of the `simulation.simulation_result_ref` Attribute and failed with `unexpected_mutation_hits=0`. Their exact outputs are retained rather than upgraded to PASS.

## Earlier end-to-end attempts

Two failed producer/consumer attempts are retained separately under `nonpassing/`. At `d0fab1bb94f0d1492d203fe050e10dea5e1a9e40`, the consumer test imported the persister from `joint_simulation_horizon`, causing an ImportError. At `f91228be4b71059e3e5c566ea6236a55439675d2`, the consumer correctly blocked because the transport DTO excludes `world_model_record`; the test fixture had not yet rebound the already content-validated WMR from `CycleSubstrateContext`. The accepted `7ffbf5c71d6352f7712673a6591be5e553993745` test-only fix performs that validated-context rebind. These earlier failures are not inherited red and are not part of the accepted positive.

The accompanying complete recursive transport census covers four direct handoff model roots and 48 model types. Its only excluded field is `SimulationPortObservation.world_model_record`; the consumer test restores it only from the validated, content-bound cycle context. The census is included as `transport-exclude-census-7ffbf5c7.json`.

## Source, tests and environment

The implementation diff from the slice base is confined to:

- `policy-engine/src/polisyos/runtime/quality/generation_cycle.py`
- `policy-engine/src/polisyos/runtime/quality/generation_source.py`
- `policy-engine/tests/unit/remediation/test_cyc_02.py`

Its five implementation commits are `90bd99dc0f6e4b03fb55591497b6b0caa6aa6758`, `e048b7a1dfe1e7163fb220c997fcb0bc8cca4e7a`, `d0fab1bb94f0d1492d203fe050e10dea5e1a9e40`, `f91228be4b71059e3e5c566ea6236a55439675d2`, and `7ffbf5c71d6352f7712673a6591be5e553993745`. The frozen file hashes are recorded in the JSON receipt. Runtime inputs read by this path include `joint_simulation_horizon.py`, `cycle_substrate.py`, `design_problem.py`, `intervention_atom_binding.py`, `recursive_generation_cycle.py`, and the core CAS store/manifest; test fixtures come from `test_generation_cycle.py` and `test_joint_simulation_horizon.py`. Their exact hashes are in `n5-intake.json`.

The run used the root worktree's `.venv/bin/python` (Python 3.14.3), macOS 27.0.1 arm64, JAX 0.8.2 on CPU; pytest config is `policy-engine/pytest.ini` with testpaths `tests`. Exact command, environment and import origins are preserved in `positive/pytest-metadata.json`, `positive/import-origin.json`, and `positive/pytest-command.txt`. Pytest passed one test in 52.01s (36.532s testcase; 56.308s end-to-end runner). No suite-wide CYC-02 or SIM-03 run was performed. No numerical run is authorized by this handoff.

## Pattern pass and next owner

- **P01/P02:** the local producer → persisted CAS → bridge → actual default N8 consumer path is now exercised; the served route, lifecycle job/run/profile/tenant resolution and external surface remain missing from this candidate.
- **P05:** the K_sim limitation remains enforced and explicit; this result cannot become world evidence or promotion/action authority.
- **P10/P29/P32/P33/P38:** checks recompute persisted bytes/receipt identity and execute the real N8 consumer. The exact-removal controls show where marker/ref-presence proxies diverge: a false but well-shaped sibling digest or an arbitrary CAS-less digest would otherwise be accepted.
- **P27:** changes extend the existing `generation_cycle.py` owner and its canonical test file; no parallel producer/loader was introduced.
- **P35:** counts above use a full walk of the pinned evidence directory and the six-value harness declaration, not a sampled log.
- **P37:** CAS/receipt/hash and selected-engine/trajectory equality are recomputed. Expected WMR/atom/outcome identity is compared to the validated fixture context across producer and consumer processes, not to an external empirical source. Causal validity, signer authority, N9 currentness and production profile/job/tenant scope are `not_established`.
- **P40:** selected engine, trajectory, receipt and sibling digest are one identity-binding class, handled in the canonical loader rather than a per-field workaround.
- **P34/P41:** prior errors are retained and attributed to the exact attempt; none is called inherited or excluded from the denominator without evidence.

After the SIM owner changes the producer contract, rerun the frozen N5/N8 witness and the actual default consumer tests against the new candidate. Root owns the shared `generation_cycle.py` and `run_lifecycle.py` bridge leases; do not add a parallel writer there. The A2 card also requires the served-cycle tests `test_generation_cycle_serves_persisted_n5_into_default_n8_value_port`, `test_default_value_port_binds_the_actual_n5_context`, and the HTTP cycle-context test, plus B-owned N9 refusal/currentness controls. SIM-03 B26 needs its own typed higher-order residual consumer test, including the three-atom product oracle. Re-run impacted consumers after that contract lands; keep B05/B26 and full closure status open until their actual owners supply those receipts.
