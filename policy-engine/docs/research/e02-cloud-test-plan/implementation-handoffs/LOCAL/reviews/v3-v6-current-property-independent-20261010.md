# Independent V3/V6 current-property review

**Scope:** read-only source and test review from the candidate worktree. The owner identified the working source anchor as HEAD `9194a65fb59355ceac35270c869f429efc7482d8`; I did not inspect Git or run tests. This is not a final source freeze or G acceptance. The two un-applied Q1 integration-test changes are excluded until root applies them and reads back the exact source.

## Exact criteria and source fingerprints

The current task ledger `LOCAL/execution-prompts/unified-local-2026-10-09/TASKS.json` is SHA-256 `a37c75cfe09d33c1f50379d5bbfd04bdb728c990e832aec3bf19c0d17035734c`.

- **V3:** “admitted content change → same candidate WMR/N5/history; ID/write-time-only control no reissue; REQ/ACQ separate.” Findings B09, B12, B27, B28, LA-046. The same-candidate ACQ path does not close LA-046's separate REQ criterion.
- **V6:** B13, “actual producer then later independent failure; successful CAS/history/debug served reader retains typed partial/exact error; corrupt ref refuses.” A controlled source-path example does not by itself establish the source-qualified positive.

Reviewed current source bytes:

- `runtime/http/routes/runs.py` @ `5660b1ef01c76fb1dc5129b7fa1e76a3b9e0471b9b44d91764b2c8eac34fa4b8`
- `runtime/quality/generation_source.py` @ `8b399470e10afe538b87f8616b64bbf2bc512327f83c7c4483478f23c233c6bd`
- `runtime/quality/design_generation.py` @ `3cea32f0016aaccf22cb2aba2216b6ee0aefe777abc6e50548eb063a3bc84411`
- `runtime/quality/generation_cycle.py` @ `327825cd2cfffac7578b4dc36792c06bb6b672027b0d8f5d6e84732d589ea3dc`
- `tests/integration/core_runtime/test_acquisition_authority_served.py` @ `ca31ff02c080db66525b1f7cdb8f1e715f385d4f1c2318833aea81b72e142654`
- `tests/integration/runtime_quality/test_configured_candidate_simulation_served.py` @ `493cfa355ca545cd8e3c8e7928fc7746cd935ab445ff495019cfeacf14671833`
- `tests/unit/runtime/http/test_control_service_di.py` @ `78606569994f94ebe0fbc32bafa8385e9dc422f14fba5dd0a5d265f6d4ffb310`

The source-bound V6 candidate-only prototype packet is `LOCAL/decisions/v6-candidate-alternative-prototype-executed-20261010.md` @ SHA-256 `2f81390b8a246aaaafc6f8f77ea3f492d5b765d45f5d5c1d6d1680da40cbf07f`. Its current-L2 alternatives packet is `LOCAL/decisions/v6-current-l2-alternatives-20261010.md` @ `41a06eedc0181a2ad709be6465ea7855476aa76759f89a6c4dd32e2b652c8e20`.

## V3: static GO for the same-candidate source path; focused replay remains required

The GET history resolver now loads the old and new N5/V3 source records through typed, scope-bound references. When candidate IDs match, it recomputes both full semantic identity hashes and requires matching stable subject, profile selection, and candidate ID; distinct occurrence and world-model hashes; and the new source's typed origin to equal the prior source (or that source's root origin). It does not treat a truncated candidate ID alone as proof. The history projection retains `currentness_status=not_established`, `authority_purpose=candidate_observation_only`, and `publication_authority=false`.

The current served test seeds both actions from the same recorded N4 candidate, reads the persisted sources and N5 input through their owners, checks equal semantic identity with a changed occurrence/WMR, checks an admitted observation delta, and then verifies the authenticated fresh GET. Its later no-growth action keeps the same candidate/history state and has a zero admitted delta. Corrupting either the origin source or reentry receipt empties the returned history with `acquisition_action_history_integrity_not_established`. This is a source-level review of the code and assertions only; I did not run the test.

The witness is a controlled candidate-only composition with deterministic span support and explicit external owner fixtures. It does not establish legal truth, production currentness, causal calibration, or publication authority. No V3 blocker is apparent in the reviewed route/test source; record the focused run separately before any closure proposal.

## V6: keep the real-source positive open

The existing controlled `test_fresh_run_details_get_keeps_n5_and_failed_sibling_checkpoint` exercises a real route/CAS/fresh-GET lineage join using the production N4 port and recorded replay, and verifies that one persisted N5 result survives a later controlled sibling failure. Its fixture is explicitly synthetic and does not establish the required current L2 source/profile. The companion configured-source test currently asserts the withheld path honestly: `generation_unavailable`, no child profile bindings, and `historical_l2_confidence_withheld` with no forwarded confidence or credal payload.

The additional candidate-only prototype is not a positive V6 child run. It used the current typed proposal producer, but the current L6 linker refused all three proposal interventions as `candidate_scenario_selected_intervention_not_linked`; none matched the root's declared levers. The existing child producer accepts an exact `GenerationUnderAResult` with status `generated`, not an `N4CandidateScenarioProposalRun`, and correctly refuses this candidate-only proposal as `n4_recursive_child_source_untyped`. The selected historical L2 vintage was withheld, with `confidence_reproducibility=not_reproducible_under_current_rule`; the recorded probe produced zero children. That is a truthful guard outcome, not V6 success.

P40 is **SAME_CLASS_DEEPER**. Stop trying to map this recording by per-string normalization or treat the LLM target claim as a linked intervention. Reuse the generated-result contract only when a source-bound current L2 input yields a genuinely generated result and exact lever matches. Any candidate-only child contract is a separate architecture choice requiring an additive source kind, recomputed L6 write-set binding, child profile/context, persistence, and a fresh reader. The prototype packet lays out both options and the minimum discriminator; the present inputs do not justify choosing or implementing that new semantics.

## Test classification and acceptance recommendation

Do not commit the strengthened external-input-dependent positive as an unconditional unit/default test that is known to fail on the selected input. That would make ordinary verification red without a qualifying source and would obscure the actual blocker. Do not convert the red into `skip`, `xfail`, or a green guard assertion.

Keep two distinct checks:

1. A default local negative test may pass only by asserting the real withheld-source behavior: typed limitation, no confidence forwarding, no generated child/profile/N5 artifact, and a fresh reader that preserves the exact limitation. This proves safe refusal; it is not the V6 positive.
2. The positive should be a separately selected source-bound integration gate requiring a named, exact current-L2 input/profile and custody receipt in a fresh manifest. If no admitted input exists, do not run it and report the positive as **UNRUN / held**. If it is invoked and the source is missing, malformed, stale, or unlinked, preserve the failure/refusal as such. Never count an absent input or the candidate-proposal guard path as a pass.

A future positive must join the actual generated parent, exact declared child source, persisted N5/CAS lineage, later independent sibling failure, fresh parsed GET, and corrupt-ref refusal. Until that source exists, the existing controlled sibling test supports only its bounded mechanism and the external-source V6 capability remains incomplete. The prototype's observed attempt is `PROTOTYPE_NOTADMITTED`; it is not an inherited red or an adjudicated closure.
