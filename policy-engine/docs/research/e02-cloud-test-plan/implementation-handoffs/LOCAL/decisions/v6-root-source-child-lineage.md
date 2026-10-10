# V6 root-source and child-lineage patch proposal

P40 classification: SAME_CLASS_DEEPER. The earlier red result had five child-reference equality checks pass, then failed because the persisted child lineage could not be resolved. The wider property is the whole root N4 producer → persisted source → derived child identities → per-child profile/context handoff → N5 source/input/result → fresh GET path, including a completed sibling and a failed sibling.

The existing owner protocol can express this fixture without changing identity rules. `cycle_substrate_context_resolver` receives each exact derived child problem; `ConfiguredCandidateSimulationContextAdmissionOwner.admit_context` selects the profile by `cycle_job_profile_selection_ref(problem)` and builds context with `cycle_job_design_problem_ref(problem)`. The proposed test owner creates the existing synthetic profile/model fixture only after seeing that child, keyed by its exact selector. The successful child uses the existing synthetic model profile and keeps `real_profile_not_established`, `grounding_not_established`, S8 blocked, N9 not admitted, and the declared-unverified SCM assumption. The failed child receives a profile keyed to its exact selected lever but no synthetic model declaration, so it cannot imply an effect model for that child. Neither branch establishes production profile selection, causal currentness, or publication authority.

The producer seam is one optional `root_n4_generation_client` argument, passed only to the internal root-source `N4GenerationPort`. `None` preserves the current default. The pre-existing `root_n4_generation_port` is not usable for this route: `n4_proposal_only` rejects it at argument validation and it is consumed later for recursive execution. The patch supplies a separate instance of the already-available `RecordedGenerationReplayClient` to preserve independent replay cursors for root and child producer calls, loads the resulting persisted source, recomputes its child problems, checks exact ref-set equality, and uses those actual children for the two branches. The partial artifact assertion covers all three nodes (root plus both children) and binds the root node ref to the actual root problem. The second-child failure message retains the existing exact stored-error text. Test ordering selects the successful child from the presence of its typed model declaration, then fails the other actual child second; a shared operator/target predicate is not used to distinguish them. No child reference, problem, or profile selector is fabricated or rewritten.

Proposed write footprint is exactly:

- `policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py`
- `policy-engine/tests/unit/runtime/http/test_control_service_di.py`

No production caller changes, generated files, or API/DTO changes are proposed. The patch is saved but unapplied. No tests or Git commands were run.

Pre-patch source SHA-256 values:

- `generation_cycle.py`: `50e2b43125ca9d6a380ac8e772e1d114bc718357f15787fe4a85dd2967851be5`
- `test_control_service_di.py`: `ef8cec74e16bdf1167cbeca02540472e0afdcce5f1f6e67f6842b9385551b3cd`

Patch SHA-256: `6802cf64799980c7287915b904e6c6bd1cd2c40ff6fc9337395c3fbdad44aed9`

Patch transport correction: this version was regenerated as a standard unified diff with three context lines from the exact pre-patch source hashes above and the in-memory candidate. All old/context rows were checked against those source bytes before emission. The prior single-line insertion hunk failed transport validation; that is separate from behavioral verification. The regenerated patch remains unapplied and has not been test-run.
