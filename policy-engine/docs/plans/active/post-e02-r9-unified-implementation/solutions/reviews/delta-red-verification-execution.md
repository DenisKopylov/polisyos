# R13 consolidated-proposal delta red review

## Boundary and denominator

This is a bounded document-level delta review of the 13 relevant rows in `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/solutions/preferred-solutions.json`: verification rows `GYD-16`–`GYD-22` (7) and execution rows `P0-ACCEPT`, `P0-REBIND`, `FINAL-FREEZE`, `FINAL-REVIEW`, `FINAL-REPLAY`, and `FINAL-USE` (6). The complete `.tasks` array was queried for these IDs; the earlier full source census recorded all 13 as unique and matched to `tasks.json`. This delta did not rerun that census or inspect rows outside this denominator.

No implementation, tests, build, production data, or product gate was exercised. The actual accepted E02 tree remains not established; none of these dispositions grants product acceptance. External provenance guidance below is only an analogy for identity completeness, not evidence that PolicyOS output is semantically correct.

## Delta dispositions

### RXE-01 — CLOSED AT PROPOSAL LEVEL — MEDIUM — `FINAL-REPLAY`

- **Exact anchor:** `preferred-solutions.json#/tasks[task_id="FINAL-REPLAY"].implementation_steps[0..3]`, `.preferred_solution`, and `.acceptance_discriminators[3]`.
- **Delta:** Shard outputs now include rule/schema versions and exact consumed upstream artifact identities alongside run/row/input/source/tree/backend/profile. The discriminator explicitly swaps only a rule/schema version or upstream artifact and requires the affected shard to become stale and ineligible for accepted replay. The frozen candidate also binds those versions and references and rejects mutable branch aliases.
- **Counterexample tested against the proposal:** A shard produced with rule `r0` or upstream artifact `a0` cannot join a matrix frozen to `r1` or `a1`, even when source/input/backend labels match; discriminator 3 requires stale status. The original RXE-01 mismatch is therefore named and rejected.
- **Smallest coherent fix:** None remains for the identified proposal gap. At execution, the consumer must resolve and compare these identities; field presence alone would not implement the stated discriminator. No execution evidence exists yet.

### RXE-02 — CLOSED AT PROPOSAL LEVEL — MEDIUM — `FINAL-REVIEW`

- **Exact anchor:** `preferred-solutions.json#/tasks[task_id="FINAL-REVIEW"].implementation_steps[0]` and `.acceptance_discriminators[3]`.
- **Delta:** The review packet binds author and reviewer identities/roles to the exact immutable candidate; a same-principal or self-issued packet explicitly cannot satisfy independent review. Reviewer competence remains separate.
- **Counterexample tested against the proposal:** An author issuing their own correctly scoped, unchanged-candidate review is rejected by the explicit same-principal negative. This closes the original self-review bypass.
- **Smallest coherent fix:** None remains against the original self-review criterion. This establishes identity separation only; the proposal does not claim a broader institutional conflict-of-interest test.

### RXE-03 — CLOSED AS A CLASSIFICATION RULE; TASK-SPECIFIC REBIND STILL REQUIRED — HIGH — `P0-REBIND`, `FINAL-FREEZE`, `GYD-16`–`GYD-22` (and the same rule on all 13 rows)

- **Exact anchor:** Each of the 13 task rows has `input_resolution_rule`; see `preferred-solutions.json#/tasks[task_id="P0-REBIND"].input_resolution_rule`, `#/tasks[task_id="FINAL-FREEZE"].preferred_solution` and `.acceptance_discriminators[1]`, and `#/tasks[task_id="GYD-16".."GYD-22"].input_resolution_rule`.
- **Delta:** Inputs must be classified as internal engineering output/allocation, existing source record, or genuine external fact/permission. A missing native producer/bridge is assigned work, not an external blocker; only the external class can justify an external-input hold after supplier/alternative investigation. FINAL-FREEZE separately says an unresolved internal producer, unknown owner, or unselected mandatory scope blocks freeze; only genuine unavailable external facts may remain unresolved without closure credit. The former `genuine_external_inputs` catch-all is absent from these proposal rows.
- **Counterexample tested against the proposal:** If the GYD-21 validator owner or GYD-22 metric producer is missing, the rule classifies that as internal owner work and FINAL-FREEZE blocks; it cannot be converted into an external-input disposition merely because the artifact is unavailable. Conversely, required real-case permission remains a genuine external fact/permission candidate.
- **Smallest coherent fix:** No further class-level wording change is required. At accepted-source rebind, each concrete input still needs its task-specific source/owner classification and supplier/alternative evidence; this review did not establish those inputs or product owners.

### RXE-04 — PARTIALLY CLOSED — MEDIUM — `FINAL-REVIEW`

- **Exact anchor:** `preferred-solutions.json#/tasks[task_id="FINAL-REVIEW"].implementation_steps[2,4]` and `.deviation_triggers[0]`.
- **Delta:** The proposal now explicitly stops instance repair on the second finding in the same class, requires widening the mechanism or declaring a bounded residual, names the smallest missing capability and its falsifier, and folds later instances into that residual while separately reviewing new classes. This closes the prior gap where P40 was only a deviation trigger.
- **Counterexample:** The bounded-residual branch can be selected by naming a “smallest missing capability” and falsifier without expressly requiring a source-bound check that the capability does not already exist in the repository. That would still permit an avoidable residual to be declared while a reusable owner/mechanism exists.
- **Smallest coherent fix:** Require the residual record to identify the canonical owner/surface searched and confirm that the named closing capability is absent there; if absence is not established, widen/reuse the existing mechanism rather than record a bounded residual. This aligns with the local P40 requirement to confirm the capability does not exist here.

### RXE-05 — CLOSED AT PROPOSAL LEVEL — MEDIUM — `GYD-18`

- **Exact anchor:** `preferred-solutions.json#/tasks[task_id="GYD-18"].acceptance_discriminators[3]`.
- **Delta:** The post-N13b re-entry row must yield exactly `typed_deeper_terminal` and zero world-growth epoch; replacing the terminal or advancing an epoch must fail the row even if pooled distributions remain unchanged.
- **Counterexample tested against the proposal:** A depth-2 case with another terminal or an emitted world-growth epoch cannot pass the new positive discriminator. This makes the original terminal/epoch expectation distinguishing rather than relying on “correct typed terminal” prose.
- **Smallest coherent fix:** None remains for the identified criterion. Accepted-source rebind must still confirm the frozen source expectation; no case run was performed here.

### RXE-06 — PARTIALLY CLOSED — MEDIUM — `GYD-21`

- **Exact anchor:** `preferred-solutions.json#/tasks[task_id="GYD-21"].preferred_solution` and `.acceptance_discriminators[0,3]`.
- **Delta:** The proposal now requires mapping actual artifact-to-validator consumption, checking omitted artifacts, probing protected properties, and failing if a required edge is removed even when another validator still covers that artifact. This closes the earlier artifact-only coverage loophole.
- **Counterexample:** “Required” and “applicable validator family” still lack an explicit source-bound expected artifact×validator relation. If the actual-consumption map is treated as the source of applicability, removal of the GX hardening edge can be normalized as non-applicable while the artifact remains covered by another validator; the original V6 obligation is then not proven. Enumerating the artifact and validator sets separately does not determine their required Cartesian subset.
- **Smallest coherent fix:** Derive the expected artifact×validator pairs from the original V6 criteria and canonical validator-owner contracts, then compare that set with actual consumed pairs. Permit `not_applicable` only when those source criteria/contracts support it. Keep this a computed crosswalk, not a new validator registry.

## External source and limits

The [SLSA v1.2 Build Provenance specification](https://slsa.dev/spec/v1.2/build-provenance) distinguishes top-level parameters, resolved dependencies, builder identity, run metadata, and output subjects; it also states that dependency completeness is best-effort through Build L3. This supports the narrow observation that naming consumed upstream identities strengthens a replay receipt, but does not prove semantic validity, PolicyOS authority, or complete input capture. The proposal must supply those properties through its own bound consumer and original predicates.

The six requested deltas are therefore **four closed at proposal level, two partially closed** (P40 residual-absence proof and GYD-21 expected-pair denominator). Product execution, source rebind, and acceptance remain unverified.
