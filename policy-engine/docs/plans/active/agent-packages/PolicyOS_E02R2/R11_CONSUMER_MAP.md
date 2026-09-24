# R11 consumer map — blocked-disposition coherence

## Evidence boundary

Read-only census against integration snapshot 8cf3028c05438dda01ebe30225ef5119ed5637d5. The inspected product source/test paths match the Phase 0 merge snapshot. No tests, native jobs, or source edits were run for this map. Four-base JUnit is pending; these are source facts, not a claim about which base owns the Appendix A red.

A complete walk of src/, tools/, and tests/ found 5,860 Python files. A text census found 24 occurrences across five files for LoopVOIDecision or .voi_decision. The typed producer/consumer path is owned by runtime/quality/generation_cycle.py; direct behavioral consumers are tests/unit/runtime/quality/test_generation_cycle.py and tools/quality/validation/check_layer3_gy_generation_cycle_contract.py. Two other hits are unrelated acquisition voi_decision_ref fields in the N13b validator and acquisition-planner test.

Source snapshot blobs (paths relative to policy-engine/):

- src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a
- src/polisyos/runtime/quality/recursive_generation_cycle.py@ddff9abd228378166bce8437862ebe487ae00149
- src/polisyos/runtime/http/services/control/generation_cycle.py@055cca6c9424deac61fa61543143a2a2d2310b1a
- src/polisyos/runtime/quality/public_export.py@4abfb2f28b32c422ecee45966b5fdd4218489b8d
- src/polisyos/runtime/http/services/control/run_lifecycle.py@a3827ed1677df17f09827d479db7510ffdb70e6e
- src/polisyos/scientist/methods/search/voi_scheduler.py@793a835b2cc79586430dbc9494c712fa805d0757
- tools/quality/validation/check_layer3_gy_generation_cycle_contract.py@b8134aeffe3b96760e7fd9663ae9670e85391160
- tests/unit/runtime/quality/test_generation_cycle.py@4f851cb207267a13877647ef82a2b73f3a24360a

## Producer/consumer map

1. **Scheduler → N6 action.** SimpleVOIScheduler._recommended_action defaults to advance. If expected improvement per dollar is below threshold but expected information gain is positive, it leaves advance and records advance_by_information_value; zero information gain instead yields reject (voi_scheduler.py L345–396). N6 calls that scheduler through _schedule_candidate_for_execution, and decide_next_action maps the result into LoopNextAction advance | stop | escalate | blocked (generation_cycle.py L211, L4159–4219). The VOI estimate is explicitly for scheduling shadow revision and does not grant authority (generation_cycle.py L8961–8982).

2. **Cycle → blocked run record.** GenerationCycleController.run marks run terminal_status blocked on a cycle-cap breach, repeated/fake cycle, or no-retry-without-new-grammar (generation_cycle.py L3702–3726, L3745–3778). _blocked_cycle writes cycle-level next_action=blocked, refinement_decision=block_candidate, search_iteration=blocked_no_retry, and a reason; a pending scheduler action becomes blocked (L9089–9115). _fake_cycle_reason supplies duplicate-cycle reason (L9166–9176).

3. **Run → N9/promotion and board.** After the loop breaks on a block, run still computes current summaries, calls _promote_completed_generation, applies its result, and derives decision/research/quarantine/portfolio fronts, with no terminal_status guard (generation_cycle.py L3761–3811). N9 independently performs subject, epoch, open-world, and evidence admissions (L4020–4105), but its owner call does not receive the outer blocked disposition. The decision front is built from N9-certified current-valid summaries (L9208–9238); summary promotion uses certified candidate IDs (L9241 onward). Confirmed source fact: blocked runs invoke N9 and summary projection. Not established: that N9 necessarily emits a receipt; its own gates may refuse.

4. **Validator → recursive terminal.** validate_generation_cycle_run recomputes each cycle’s expected terminal from grounding/value evidence and permits only scheduler actions in its denominator plus pending, blocked, and unsupported_terminal (L5913–5954). For every adjacent equal content hash it unconditionally emits fake_cycle_same_candidate_repeated, even when the run and last cycle record that repeat as blocked (L6004–6019). It does not reconcile run terminal_status/blocked_reason with final VOI action, refinement decision, search iteration, or promotion output. generation_cycle_terminal_state maps run-level blocks to budget_exhausted for the safety cap or recursive_blocked otherwise (L6094–6116). The recursive owner validates before making a leaf; any issue raises recursive_leaf_generation_cycle_invalid (recursive_generation_cycle.py L907–929). A valid leaf terminal is owner-derived and equality-checked against generation_cycle_terminal_state (L371–377, L536–538). Therefore the current duplicate issue prevents the typed blocked terminal from reaching recursive routing.

5. **HTTP/public projection and lifecycle.** The served composer iterates leaf OWR limitations and promotion receipts, then serializes the recursive run (runtime/http/services/control/generation_cycle.py L671–744); no explicit blocked-run condition guards those loops. project_pre_n9_open_world_limitations validates the run and checks a specific not-promoted OWR reason plus empty receipt/certification sets, but has no blocked-disposition predicate (public_export.py L214–271). run_lifecycle collects promotion refusal reasons, publishes a manifest, and reports job-processing state completed (run_lifecycle.py L3342–3374). That job state does not itself establish policy authority, but these consumers add no blocked-vs-N9 coherence rule.

6. **Contract checker and tests.** The GY-N6 checker captures serialized VOI decisions (check_layer3_gy_generation_cycle_contract.py L847–871). Its mutations test advance changed to stop and unknown scheduler-action rejection (L874–906, L920–922, L1041–1049); it lacks a blocked-disposition mutation, a repeated-candidate acceptance-only-when-blocked mutation, or a blocked-run N9 leakage mutation. The owner validator is the existing behavioral truth source.

The R11 test fixture emits candidate_cycle_2 with voi_estimate 0.41 at test_generation_cycle.py L359–372. While its counterexample grammar token is present, later calls return the same candidate/hash (L343–388). The test asserts first action advance and expects the last action stop/escalate (L3213–3261), but does not pin coherent blocked-run validation or exercise a served recursive leaf. This is source-level scheduler/test-fixture evidence only. Whether .41 explains the reported Appendix A result and which bases pass the file remain pending four-base JUnit.

## Property, P37/P38, controls, falsifier

**One P40 property:** an N6 blocked disposition is one owner-owned state across cycle record, run validator, N9/promotion result, candidate fronts, serialized projection, and recursive terminal. A coherent block remains replayable and visible as a typed limitation; it cannot be relabeled completed or yield N9 authority from that blocked run. Candidate-band computation and honest stop/advance remain usable. An unblocked repeated candidate must still be rejected. The duplicate validator refusal and unconditional post-loop N9 invocation are manifestations of this same coherence class, not separate instance fixes.

**P37 predicates.** The duplicate detector recomputes equal content hash from adjacent cycle records. The validator recomputes expected terminal and scheduler-action membership, but the conjunction for a coherent blocked disposition (run status/reason ↔ final VOI/refinement/iteration ↔ no N9 authority) is not established. N9 recomputes its own candidate/epoch/evidence predicates, but does not receive run terminal status. Recursive terminal is owner-derived from run status, but is unreachable when the earlier validator rejects the leaf.

**P38 divergence.** The property concerns whether a blocked N6 run can be validated, projected, and promoted coherently. The implementation treats repeated hashes as unconditionally invalid, tests action vocabulary and selected local invariants, yet calls N9 after the block and traverses receipts in served projection without a blocked branch. Distinguishing case: duplicate cycle is explicitly marked blocked with all _blocked_cycle markers intact; validator rejects it while producer has entered N9. Marker presence or allowed-action membership does not prove disposition coherence.

**Removal probe (behavioral, markers retained).** Use the real repeated-candidate fixture. Keep blocked_reason, final block_candidate, blocked_no_retry, and VOI reason markers, but corrupt one owner linkage (for example, set run terminal_status=completed while keeping final cycle blocked markers). Require the canonical validator/contract gate to turn red. Also run the coherent blocked form through recursive routing and assert the serialized typed terminal survives and no promotion receipt/certified decision front is emitted. The probe must fail if the coherence predicate is removed while markers remain.

**Property-preserving controls.** Existing test_terminal_projection_preserves_stop_budget_and_abstention requires normal stop to remain stop and distinguishes it from abstention (test_generation_cycle.py L3735–3759). Preserve an ordinary advancing counterexample-driven candidate-band run. test_controller_refuses_live_retry_without_new_grammar is a useful blocked-path control, but does not cover duplicate validation or N9 suppression (L3457–3479).

## Proposed safe write set

Make one owner-level change in runtime/quality/generation_cycle.py: validate one coherent blocked-run state, prevent a blocked run from entering authority-producing N9 admission, and derive candidate/terminal projections from that state. Reuse the current validator and N9 owner; do not add parallel authority.

Witness candidates:
- tests/unit/runtime/quality/test_generation_cycle.py: repeated-cycle removal probe, honest-block acceptance, ordinary stop/advance controls.
- tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py: served leaf carries typed block and no authority receipts.
- tools/quality/validation/check_layer3_gy_generation_cycle_contract.py: behavioral mutations for incoherent blocked disposition and blocked-run N9 leakage.
- Touch runtime/http/services/control/generation_cycle.py or runtime/quality/public_export.py only if the served witness shows the owner artifact loses the block; current HTTP serializer carries the recursive run.

Sequence generation_cycle.py after active R1/R2/R5/R12/R13 writers; the generation_cycle.py test file also needs serialized ownership after its active writers. The checker and recursive test can be reviewed independently, but final change should preserve one invariant. No source/test files were modified for this census.

Source-order question for implementation: after run marks a repeated cycle blocked, it still processes that cycle’s N7 route/acquisition request before reaching the blocked break (generation_cycle.py L3721–3763). Whether a relevant request occurs is a runtime question; inspect as part of the boundary, not a proven R11 regression.

## Baseline status

- **Confirmed source facts:** scheduler information-gain branch; .41 fixture value; explicit cycle/run block markers; unconditional post-loop N9 call; unconditional duplicate-hash validator issue; validator-before-recursive-terminal ordering; serialized receipt traversal.
- **P41 pending:** whether 78187878e and main pass the base test, whether E02/integration produces the reported blocked outcome, and whether this file has a relative pass→fail under the real worktree/data conditions. Do not change the base test expectation until the four-base result and typed-disposition evidence agree.
- This map is not a decision that blocked was the intended base behavior.
- Pattern pass: P04, P27/P31, P29/P32, P37/P38. Acceptance must be a behavioral witness across owner, validator, projection, and recursive consumer.
