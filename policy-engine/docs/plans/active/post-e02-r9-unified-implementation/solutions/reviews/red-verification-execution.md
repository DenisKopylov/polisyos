# R13 execution + verification proposals: red-team review

## Review boundary and denominator

Reviewed only the two R13 proposal JSON files against the original `tasks.json`, `execution/07-scoped-readiness.md`, `solutions/README.md`, `solutions/00-shared-decisions.md`, and the GY Phase 7 source criteria. The complete proposal denominator is **13 JSON task rows**: `verification-proposal.json` has 7 (`GYD-16`–`GYD-22`), `execution-proposal.json` has 6 (`P0-ACCEPT`, `P0-REBIND`, and `FINAL-FREEZE` through `FINAL-USE`); all 13 IDs are unique and each matches one original `tasks.json` row. Measured by `jq` over those complete JSON arrays and the complete `tasks.json.tasks` array.

This is a documentation red-team review only. Product execution remains UNRUN; the brief says the actual accepted E02 tree is not established. I did not run tests/builds, inspect production data, or read product source code. Findings below do not grant task or product acceptance.

## Findings

### RXE-01 — MEDIUM — Final replay shard receipts omit the frozen rule/schema identity

- **Task IDs:** `FINAL-REPLAY`
- **Bucket:** Same provenance/identity class one level deeper (`P07`): freeze identity is named, but the emitted shard receipt is not expressly bound to every frozen semantic version.
- **Exact anchors:** `execution-proposal.json`, `FINAL-REPLAY.implementation_steps[0..2]` (lines 369–372), and `FINAL-REPLAY.acceptance_discriminators[0]` (line 400). The freeze record separately names rule/schema versions in `FINAL-FREEZE.preferred_solution` and implementation step 2 (lines 211, 235).
- **Finding:** The root freezes rule versions, but the shard output identity is described as run ID, row IDs, input refs, source/tree, and backend/profile. The positive join criterion names source/input/backend-qualified output. It does not say that each emitted output carries or resolves to the exact frozen rule/schema version (and consumed upstream artifact identities).
- **Counterexample:** A rule is versioned in an owner/config artifact outside the code tree. A shard generated under rule `r0` has the same tree, case input, backend, and profile as the final matrix pinned to `r1`; the stated receipt fields still match and can be joined unless `input_ref` is guaranteed to identify `r1`.
- **Smallest coherent fix:** Add rule/schema version and required upstream output IDs to the shard identity, or state that `input_ref` is an immutable reference that resolves to those exact versions and require the consumer to compare them to the frozen row. A mismatch must remain stale/unverified. This closes the identity gap without adding another replay system.

### RXE-02 — MEDIUM — Final review does not exercise its explicit self-review negative

- **Task IDs:** `FINAL-REVIEW`
- **Bucket:** Same review-provenance class one level deeper (`P14/P38`): reviewer-to-scope binding is present, but independence from the author/producer is not measured.
- **Exact anchors:** Original `tasks.json` `FINAL-REVIEW.adversarial` at line 9288 says a self-reviewed packet cannot enter final replay. The proposal rejects self-review in prose (preferred solution/alternative, lines 279 and 306–309), but its adversarial discriminator is only post-review scope mutation and its removal probe only removes the reviewer-to-scope binding (lines 326–329). Step 1 says to capture review identity and scope (line 301).
- **Finding:** The proposed review packet binds a reviewer to a scope, but the deciding negative never binds reviewer identity against author/producer identity. “Independent” remains a label in the acceptance statement rather than a discriminated relation.
- **Counterexample:** The change author is also recorded as the reviewer; the packet has the right scope, criterion, source and unchanged tree. The proposal’s reviewer-to-scope removal probe still passes, although the original self-review adversarial must fail.
- **Smallest coherent fix:** Bind reviewer principal and author/producer principal for each reviewed scope; add the same-identity packet as a negative that cannot enter replay. Keep competence as a separate field. Do not add another independent execution engine: the missing property is reviewer identity separation.

### RXE-03 — HIGH — Internal source and verification work is classified as `genuine_external_inputs`

- **Task IDs:** `P0-REBIND`, `GYD-16`–`GYD-22`; the classification also affects how `FINAL-FREEZE` treats unresolved rows.
- **Bucket:** Same scope-classification class already called out in `solutions/README.md` (line 27): missing bridge/parser/validator/migration work is internal engineering, not an external input.
- **Exact anchors:** `execution-proposal.json#/task_solutions[task_id=P0-REBIND].genuine_external_inputs` (lines 194–197); `verification-proposal.json#/task_solutions[task_id=GYD-16..GYD-22].genuine_external_inputs` (lines 213, 287, 362, 432, 509, 586, 661); `FINAL-FREEZE.acceptance_discriminators` permits a source-qualified unresolved external disposition but says missing internal owners block (lines 258–260).
- **Finding:** Several entries mix a genuinely external act with artifacts or work owned by the repository: the complete GY-acted denominator; canonical inventories and post-rebind path/reader observations; N10/N13b artifacts and certificate-owner resolution; test fixtures; V2 persisted runs and replay profile/rule bindings; the artifact/validator set and Task-0/16-audit scope; and G8 metric snapshots, known-seed corpus and index-freshness evidence. These are internal source discovery, production, verification or composition tasks. E02 acceptance itself, lawful real-input/site permission, externally authorized case selection, and an institutional decision can remain external.
- **Counterexample:** The GY-21 validator inventory or GY-22 metric snapshot producer has not been located/built. The proposal labels the validator commands or metric snapshots external; FINAL-FREEZE can then carry an unresolved external disposition instead of recording `verification_missing`/`producer_missing`, despite these being internal owner work. The freeze discriminator helps only if the classification is independently corrected before it is used.
- **Smallest coherent fix:** Split each row into (a) competent external acts/permissions/evidence and (b) internal upstream artifacts, inventories, producer/consumer work and owner resolution. Keep the accepted E02 G decision as the external entry warrant, but treat the accepted tree, task denominator, validators, corpus, rules and metrics as source-bound internal inputs. Missing internal pieces stay open with their capability labels and block freeze when selected.

### RXE-04 — MEDIUM — P40 is named as a trigger, without its required second-finding disposition

- **Task IDs:** `FINAL-REVIEW`
- **Bucket:** Same class one level deeper (`P40`): a “second finding of the same class” is noticed, but the class-level stop/closure move is absent.
- **Exact anchors:** `FINAL-REVIEW.implementation_steps[2]` classifies new vs known and batches/delta-reviews findings (line 303); `deviation_triggers[0]` names “second finding of the same class” (line 336). The pattern pass in `solutions/README.md` includes P40 (line 35), whose rule is to stop per-instance repair on the second same-class finding and widen the mechanism or declare a bounded residual with a falsifier.
- **Finding:** The second occurrence is only a deviation trigger. Nothing says what happens at that trigger; the ordinary “batch blocking fixes and delta-review” path still applies. This leaves the repair ladder able to continue one checker/consumer deeper at a time.
- **Counterexample:** The first review finds an omitted-property check in validator A; the second finds the same missing invariant in validator B. The current procedure can patch B and repeat review, even though the two findings establish one class that needs a wider owner-level mechanism or an explicit residual.
- **Smallest coherent fix:** On the second same-class finding, require a written NEW-vs-same-level classification and stop instance repair. Either widen to the property’s actual owner/consumer set, or record the bounded residual, its smallest closing capability and a falsifier proving that capability is absent. Later examples of that declared class consume no new repair round.

### RXE-05 — MEDIUM — GYD-18 does not pin the required post-N13b terminal/epoch result

- **Task IDs:** `GYD-18`
- **Bucket:** Same status/property class one level deeper (`P04/P10`): a case is required, but its original typed disposition is not explicit in the proposed acceptance discriminator.
- **Exact anchors:** Original `tasks.json` GYD-18 positive at line 2990 says “post-N13b case is typed deeper terminal.” The source GY Phase 7 criterion pins the frozen N13b label as `typed_deeper_terminal` with **no world-growth epoch** at `GY-engine-subordination.md` lines 5553–5558. Proposal GYD-18 says “at its true depth” (line 304), “correct typed terminal/limitation” (line 329), and only requires representation at the required depth (line 358).
- **Finding:** The solution preserves case inclusion/depth but does not carry the exact frozen N13b terminal and no-epoch condition into the positive readout. “Correct typed terminal” is not a distinguishing discriminator unless it is bound to the original expected label and epoch state.
- **Counterexample:** The N13b case appears at depth 2 but is labeled with a different terminal, or a new world-growth epoch is emitted; it can still satisfy “represented at required local/recursive depth” and be counted in the distribution.
- **Smallest coherent fix:** Bind the N13b row to its source-owned expected terminal `typed_deeper_terminal` and assert no world-growth epoch for that frozen run. If accepted-source rebind changes that expectation, record the source-bound delta rather than accepting any typed terminal.

### RXE-06 — MEDIUM — GYD-21’s “applicable validator family” lacks an expected pair denominator

- **Task IDs:** `GYD-21`
- **Bucket:** Same gate-predicate/proxy class one level deeper (`P37/P38`): the set of validators is enumerated, but the expected artifact-to-validator relation is left implicit.
- **Exact anchors:** Original `tasks.json` GYD-21 deliverable/final property at lines 3214 and 3257 require every GY artifact through the full validator set. The source GY V6 criterion at `GY-engine-subordination.md` lines 5598–5602 says every artifact passes the GX hardening validator and the Task-0, 16-audit and GY-V validator suites are green. Proposal GYD-21 says to map actual validator consumers (lines 529, 550–554), but positive acceptance is only that every artifact is consumed by its “applicable real validator family” (line 582).
- **Finding:** The full artifact and validator denominators are present, but no source-bound expected artifact×validator applicability set is named. If actual current consumers define applicability, the readout can describe a missing required relation as “not consumed/applicable”; running every known validator once does not prove that every required artifact was passed through its required GX/audit check.
- **Counterexample:** A GY artifact still has some generic consumer, but its input binding to the GX producer-root validator has been removed. The validator runs once against its remaining inputs and the artifact-to-actual-consumer map shows another verifier, so no artifact is orphaned; the original requirement that the GX hardening property cover that artifact is nevertheless unproved.
- **Smallest coherent fix:** Derive the expected artifact×validator pairs from the original V6 criteria and canonical validator contracts, then compare them to the actual inputs consumed. Record source-qualified `not_applicable` only when the original property/owner contract supports it. Keep this as a computed crosswalk, not a new validator registry.

## Preserved constraints / no finding

- `P0-ACCEPT` remains the sole actual E02 G entry warrant; the proposal binds the G decision to accepted commit/tree, scope, inputs, backend and limitations. This does not establish that the decision exists or that any product gate passed.
- `P0-REBIND` keeps scoped release in the existing root journal and retains whole-program reconciliation before `FINAL-FREEZE`. This matches `execution/07-scoped-readiness.md` lines 7–15 and avoids treating R12's scoped stage correction as global completion.
- `GYD-18`/`GYD-20`/`GYD-22` retain their interface-agreement preparation edges and actual GYD-17/GYD-18 completion dependencies in `tasks.json`; `FINAL-REPLAY` joins LIF-09 and GYD-16–22 at completion rather than making them global start barriers. The proposals explicitly call these completion witnesses and require selected conditional bindings to carry artifact or typed absence, owner, consumer, surface, stage and exact input (`execution-proposal.json`, `FINAL-REPLAY`, lines 347, 394–397). No second scheduler or per-lead ledger is proposed; the existing root journal and stage resolver remain the owners.
- Migration/readback language generally preserves historical outputs and candidate identities; no migration-denominator issue was confirmed within these 13 rows beyond the explicit V3 terminal and V6 validator-pair gaps above.

## External primary-source checks (web, 2026-10-22)

- [SLSA v1.2 Build Provenance](https://slsa.dev/spec/v1.2/build-provenance) distinguishes build definition, external parameters, resolved dependencies, builder and output subject; it says external parameters are untrusted and must be verified downstream. Its resolved-dependency completeness is best-effort through Build L3. The proposal correctly treats it as an identity analogy, not proof of PolicyOS semantic validity.
- [OCI Descriptor](https://specs.opencontainers.org/image-spec/descriptor/) defines digest and byte size for referenced content and recommends checking both when consuming it. This supports GYD-17/20 byte binding only; it does not support semantic/authority claims, which the proposal correctly keeps separate.
- [GitHub merge queues](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue) run checks for temporary merge groups containing the latest target and queued changes. The execution proposal uses this only to motivate binding checks to the integrated tree.
- [Airflow trigger rules](https://airflow.apache.org/docs/apache-airflow/stable/concepts/dags.html#trigger-rules) distinguish upstream tasks being done (`all_done`) from all succeeding (`all_success`). This supports a terminal-outcome join separate from acceptance; it does not define PolicyOS acceptance.
- [Software Engineering at Google, “Large-Scale Changes”](https://abseil.io/resources/swe-book/html/ch22.html) describes dedicated sharding, review, test and cleanup infrastructure at Google scale. The proposal states those scale/tooling limits and does not propose importing that platform.
- [SOURCE_DATE_EPOCH](https://reproducible-builds.org/docs/source-date-epoch/) documents controlling build-time timestamps. This supports only the narrow timestamp-normalization example, not complete or semantic replay reproducibility.
