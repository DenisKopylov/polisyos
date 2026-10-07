# Independent A runtime-property review

**Disposition:** source review only. I did not run tests, modify source or refs, or inspect production data. The source candidate reviewed is A commit 1590f35b6817c46af484de818ba227517c5a8d1b, tree 1ba0de8ff3363431781c69923de7cb13e9fa892f, parent 9e495b2955c1b662ddaaa1cde3e0e9fddd59f685. This is not G's current HEAD and is not yet an integration acceptance. G was at 9806442ddb47d624a2940bac75d9d6248e934c48 when I checked. The A delivery worktree contains later uncommitted material, which I excluded by reading candidate blobs with git show <sha>:<path>.

I read the original A criterion cards at the pinned main source checkpoint, the A continuation progress, wave-2 check/source-review receipts, and the N5/N8/model-revision/recursive evidence. The required result-pack integrity check returned ok; verification.json reports the planned 2,074 Python file/cut cells and 282 findings, with no raw archives. The complete A denominator is 13 bundles, 34 unique finding IDs and 35 source occurrences; the candidate progress file labels all 34 source closures not adjudicated. I did not infer closure from that denominator or from source summaries.

## B10/B11: hard feasibility before VOI — bounded source GO; candidate execution still required

The candidate implements a meaningful path for the ordinary default NCM simulation route. GenerationCycleController prepares a request from the grounded candidate and owner context, assesses applicability using the existing joint-simulation horizon owner, binds the prepared request to candidate/problem/cycle, and rechecks the binding before N5 executes. The selection path excludes candidates with hard applicability conflicts; when every candidate is infeasible the path returns before N5 and before the later VOI decision. A not-run hard-feasibility result is explicit. This uses the existing NCM owner and generation cycle; it does not introduce a second simulation engine or treat a score as authority.

The new tests/integration/core_runtime/test_e02_hard_feasibility_before_voi.py is a real runtime/CAS/readback test, not a marker scan. It sets a higher-ranked conflicting candidate against a lower-ranked feasible one, checks that the feasible candidate is selected and its actual simulation result is persisted and consumed by a fresh N8 process, and checks that all-infeasible candidates make zero N5/VOI calls. The removal control removes the applicability filter while preserving refusal markers and demonstrates the rejected candidate being selected. It also covers request digest changes, non-finite numeric rejection and legacy injected-controller shape.

This is bounded to the default owner-built ncm_parallel_worlds request route. It intentionally does not establish hard-feasibility behavior for arbitrary custom controllers, caller-provided factories, all engines, or every recursive candidate path. That boundary is acceptable for a bounded default-path implementation claim, but the original B10/B11 wording is broader than this one mechanism. Do not report universal search feasibility, measured VOI, production outcomes, or closure from the fixture.

**Acceptance check:** run the exact candidate in an isolated checkout and retain full origin/output receipts for:
- tests/integration/core_runtime/test_e02_hard_feasibility_before_voi.py (all cases; or at minimum test_hard_n5_feasibility_filters_before_voi_and_serves_real_owner_result, test_all_hard_infeasible_candidates_block_before_n5_and_voi, and test_removing_candidate_filter_keeps_refusal_marker_but_selects_refused_candidate).
- Reconcile the test and runtime source blobs with candidate 1590f35...; do not reuse the old N5 receipt as this candidate's PASS. The prior N5 receipt targets 6565fcd... and its generation_cycle.py and test blobs differ from this candidate. Likewise the later 355-test wave at d273... is not this source candidate.

## B04/B05/B08: N8 intake binding — bounded helper GO; standard positive surface remains unproved

The N8 objective-intake change reconstructs the expected N5 candidate, outcome and atom identities from current candidate inputs and compares them with CAS-resolved N5 content before producing the evaluation input. The simulate-only path refuses unknown/fatal blockers and a tampered persisted reference before the owner gateway. This preserves the distinction between “usable as a model-conditioned simulation” and “world evidence”: clearing blockers or changing K_sim into K_world is not an acceptable fix.

The wave-2 receipt for 069ceaa7af2dba02f1cb303a251a03c3095b6bbc (tree 6d47aefc789db4e1bdb6d53d1af7722f0c4ac643) records the focused N8 checks and a binding-removal red. It is an ancestor of A's current candidate, but the candidate's test_value_gate.py blob is now 830c148c..., versus 5c124e52... in that receipt. Treat that receipt as design/history evidence, not a test of candidate 1590.

**Acceptance check:** exact-candidate replay of the four defining selectors in tests/unit/runtime/quality/test_value_gate.py:
- test_n8_intake_rejects_outcome_candidate_and_atom_mismatches
- test_foundry_value_port_recomputes_actual_n5_outcome_and_atom_bindings
- test_simulate_only_n8_rejects_unknown_or_fatal_n5_blocker_before_owner_gateway
- test_simulate_only_n8_rejects_tampered_persisted_n5_reference_before_owner_gateway

The available proof is a conditional model-value path. B04's full criterion also requires another allowed consumer after reopen; B05 requires the same simulation to remain unable to establish empirical/world effects; B08 requires the ordinary default consumer's positive conditional branch and its refusal of unsupported empirical claims. The cited tests do not establish the complete ordinary served path, a real-world effect, or the entire B04/B05/B08 bundle. Keep those findings limited until the exact ordinary consumer contract is demonstrated.

## B09: candidate model revision — narrow mechanism proven on matching source blobs; whole re-entry criterion limited

The source prevents a same-name retry from reaching N5 unless the materially consumed model basis changes, and carries the new basis through the candidate re-entry path. This is a plausible reuse of existing generation-cycle/history machinery. The receipt for 01e465e25577eb285fefc06e4e8d3ce5dd430e86 has one passing integration test; its test blob (6879f98a...) and generation_cycle.py blob (9cb88715...) exactly match candidate 1590. The receipt therefore supports this narrow code path, though it is not a complete run of candidate 1590's import closure.

The test manually invokes candidate-model re-entry with a synthetic model. It does not prove automatic ordinary history transition on real changed data, or that the next validator consumes the revised occurrence. Keep B09 limited to the changed-basis gate until that lifecycle is shown. B27/B28 are not established by this test.

**Useful exact selector if the candidate import closure changed:** tests/integration/runtime_quality/test_e02_candidate_model_revision.py::test_same_candidate_model_revision_reenters_only_for_changed_semantics. Do not repeat it solely to claim broader factual or production validation.

## Recursive budget/frontier and checkpoint — semantic core exists; ordinary served producer is not demonstrated

At candidate 1590, the recursive frontier tests assert that a budget-stopped child retains the completed child and pending sibling, distinguishes a controller budget stop from N8 epistemic abstention, and rejects a self-asserted internal-parent terminal in a partial V2 checkpoint. These are meaningful typed-state assertions over the actual recursive controller and checkpoint validator. They are more than shape/marker checks.

The companion test_e02_recursive_partial_readback.py obtains a real fixture/controller partial artifact, then manually inserts that artifact through the owned control-job/Core-CAS path and verifies a fresh run-details GET resolves it, projects the partial frontier and does not fabricate a root terminal. Its module docstring and body explicitly leave the ordinary POST/worker path untested. Therefore the tested chain is controller fixture → manual owned-job insertion → Core/CAS → fresh GET, not the normal served producer path.

The later recursive receipt at 65926cb5aa5364ff0e54741ea6689a16e9ed14b0 is on a divergent lineage (not an ancestor of 1590); it cannot certify the reviewed candidate. Candidate 1590's test blobs are 13e8fb09... (frontier) and ad1872e4... (readback). Do not transfer later v2 fixes or PASS labels backward.

**Exact-candidate checks required before accepting this slice:** run both files:
- tests/integration/runtime_quality/test_e02_recursive_budget_frontier.py
- tests/integration/core_runtime/test_e02_recursive_partial_readback.py

A passing replay would support the bounded typed budget/checkpoint mechanism, not the ordinary production route. Whole recursive closure still needs either a normal served worker/POST consumer demonstration or a precise documented surface_out_of_scope for that path. Do not demand production data just to prove the finite budget rule.

## N7 acquisition / LA-046 — compiler and re-entry wiring are real; data admission and world growth are separate

Candidate 1590 has a configured persisted capability-index resolver, typed errors when its release is unavailable, and generation-cycle branches that derive N7 requirements without test hints and record same-cycle re-entry. There are meaningful existing candidate-band routes; N7 is not absent. A typed requirement, nonempty spec, job, URL, or receipt alone is not a measurement admitted into the world.

The currently bounded N7 source path uses the configured C capability index/resolver. A binding identifies capability compatibility; it does not grant source authority, license, permission to act, or admission of a measurement. Empty specs correctly do not mean completed acquisition. Current tests use controlled registries/payloads and establish route behavior, not owner-signed source/profile rights or a content-bound C-admitted observation that changes the same-cycle dependent N5/WMR result. The existing bridge can proceed within its stated candidate band. The external source/profile/variable/permission and admitted-row evidence remain C/owner inputs where the original criterion requires them; do not manufacture them by adding generic labels or querying production during this review.

**Minimum exact-candidate route check:** tests/unit/runtime/quality/test_e02_configured_n7_resolver.py, plus the focused generation-cycle selectors test_acquisition_required_derives_n7_inputs_without_test_hints_and_reenters, test_acquisition_required_invokes_n7_and_records_same_cycle_reentry, and test_default_production_n7_without_runtime_store_keeps_typed_limit. To claim actual acquisition/world growth for B12, add only the owner-authorized admitted-row consumer test once that input is available; the unit fixtures cannot substitute for it. LA-046's two source occurrences in REQ-01 and ACQ-01 remain distinct.

## Decision and pattern accounting

- **Source review:** bounded GO for the default NCM pre-VOI mechanism and the N8 candidate/outcome/atom binding helper; limited for candidate model re-entry; partial recursive checkpoint behavior is credible but lacks the ordinary served producer on this candidate; N7 route exists but does not prove native admitted data/world growth.
- **Whole findings:** no new finding is closed by this review. B10/B11 are not universal search claims. B04/B05/B08 remain limited as a bundle. B09 remains limited. B12 remains producer/consumer bridge incomplete until a same-cycle admitted observation is consumed; real source authority is an owner input, not an A-owned code fix. LA-046 stays limited and its REQ/ACQ occurrences remain separate.
- **Relevant patterns:** P01/P02 producer-bridge reality; P04/P05 authority and status separation; P07/P08 replay and temporal basis; P10 semantic adequacy; P14 independent evidence; P29 behavioral proof; P32 trust-by-form; P37/P38 classify recomputed versus owner-supplied gate predicates and state the proxy divergence; P41 do not inherit unrelated candidate receipts.
- **Minimal next wave:** isolate exact commit 1590 and run the N5 defining file, four N8 selectors, both recursive files, and the four N7 route selectors above with candidate-local module origins and complete output. Reuse the matching model-revision receipt unless dependency reconciliation reveals a changed import. Do not run the 34-finding suite or production lookups for this bounded runtime review.
