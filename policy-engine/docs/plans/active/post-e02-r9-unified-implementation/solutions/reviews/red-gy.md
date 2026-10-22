# R13 GY red-team review

Review target: `gy_core-proposal.json` and `gy_learning-proposal.json` under `_build/post-e02-r13-solutions-20261022/`, reconciled against original `tasks.json`, GY source criteria, the shared solution decisions, adopted B01/C01/C02 and S0-K14. This is a planning-document review, not an E02 source rebind, code review, or product acceptance.

Scope census: `jq` walked the complete `.task_solutions` arrays in the two JSON proposal files (file-type denominator: 2 proposal JSON files): `gy_core-proposal.json` contains 18 IDs; `gy_learning-proposal.json` contains 8 IDs; 26 total, exactly GYD-01–15 and GYD-23–33. E02 acceptance remains `not_established`; all static source anchors are provisional until task-scoped accepted-source rebind.

## Findings

### RGY-01 — Do not reopen already accepted ADRs by default

- **Severity:** Medium
- **Bucket:** New class — adopted-decision re-open by stale imperative.
- **Task:** GYD-01.
- **Exact anchors:** `gy_core-proposal.json#/task_solutions/0/preferred_solution` (“Amend ADR-0178/0179 at the competent owner”) and `#/task_solutions/0/implementation_steps/0` (“Resolve amended ADRs”); compare accepted ADR-0178, status/date and its controlling 2026-09-17 D2.3/D6 amendment (`docs/adr/0178-promotion-posture-admission-resolves-owner-artifacts.md`, §§Status, Amendment, Revised D2.3/D6) and accepted ADR-0179 (`docs/adr/0179-correspondence-vocabularies-meaning-principles-first-profiles-open.md`, §§Status, Decision, open first profiles). The integrated task already says “Resolve amended ADR-0178/0179” (`tasks.json:1798`) and the workstream says protected admission follows that amended conjunction (`workstreams/03-gy.md:5`).
- **Counterexample:** An implementer reads “Amend” as a new normative decision, reopening fixed S6 evidence requirements or ADR-0179’s accepted meaning principles even though the existing accepted texts already control. The actual open items are named profiles/appointments and evidence, not a blanket missing decision.
- **Minimal coherent fix:** Replace the imperative with “rebind and apply the currently accepted ADR-0178 (including its controlling amendment) and ADR-0179 principles; escalate only if a named revisit trigger or a genuinely unresolved profile changes the claim.” Keep PR1a, protected PR1b and the authentic GY-O0-NC-01 near-miss distinct. A competent principal decision remains external only where the accepted ADR leaves that exact protected choice open.

### RGY-02 — Separate external evidence from internal engineering and owner allocation

- **Severity:** High
- **Bucket:** One repeated class (`internal work/output represented as genuine external input`); same class across task rows, not one new defect per occurrence. The second occurrence is the stop point under P40: widen the classification once for the whole proposal set; subsequent rows below are examples, not additional repair rounds.
- **Tasks:** Confirmed in GYD-02, GYD-06, GYD-07, GYD-12, GYD-13, GYD-15, GYD-25, GYD-26, GYD-30, GYD-31 and GYD-33.
- **Exact anchors:** `gy_core-proposal.json#/task_solutions/1/genuine_external_inputs` includes the canonical writer; `/5` requires an appointed producer; `/6` calls routed owner repairs external; `/9` lists the freshness owner; `/10` lists the actual judge output and consumer contract; `/14` lists actual callers/results/fresh consumers; `/15` lists actual consumer behavior; `/17` lists accepted consumer contracts. `gy_learning-proposal.json#/task_solutions/4/genuine_external_inputs` includes branch-head state and later-cycle readback; `/5` includes the CB1 instrument/corpus and canonical event-store receipt; `/7` includes the cutoff primitive and owner-resolved receipt source. These fields mix actual source/authority facts with local owners, mechanisms, receipts and required product outputs.
- **Counterexample:** GYD-15 requires an independently enforced cutoff primitive as an input to the capability whose task is to build that cutoff chain; GYD-06 can wait for a producer appointment instead of implementing the missing producer/admission route; GYD-07 can misread routed internal owner repairs as external facts and defer even validator/bridge work that can be prepared before the final pass. Likewise, a real GYD-26 judge output or GYD-30 fresh consumer is a required local result, not evidence supplied by an external institution.
- **Minimal coherent fix:** In the recommendation prose, separate (a) genuinely external facts or acts (for example, permitted real observations, institutional trust/mandate evidence, or a real operator event), (b) internal engineering prerequisites/artifacts, and (c) internal owner allocation or upstream completion joins. Assign/build the latter through the existing task owners and scoped stages; keep final composed acceptance blocked when its real source fact is absent. If the source itself is genuinely unavailable, preserve the exact gap/refusal and do not synthesize a positive. Do not split this into per-task patches: apply this one classification correction across the rows above.

### RGY-03 — AS2’s “holdout-tuned scores no better” discriminator is not operationally defined

- **Severity:** High
- **Bucket:** New class — under-specified scientific comparator.
- **Task:** GYD-08.
- **Exact anchors:** `gy_learning-proposal.json#/task_solutions/0/acceptance_discriminators/0`; original `tasks.json:2318–2321`; source `GY-engine-subordination.md:5731–5738`.
- **Counterexample:** “Scores no better” does not say which score (risk, coverage, or a selected operating point), which data the compared classifiers are scored on, what “unseen” means, or what adaptive selection attack is exercised. A model selected after trying many thresholds can score better on the same holdout by construction; that alone does not establish better generalization. Conversely, a correct model may tie or lose to an unseen comparator. The test can therefore fail or pass for reasons unrelated to the intended leakage property.
- **Minimal coherent fix:** Preserve the source criterion verbatim and keep WP-09/WP-10 numeric thresholds withheld, but do not claim AS2 acceptance from that sentence until the criterion owner fixes the score, comparison data, selection procedure and direction in a dated clarification. Derive the adversarial selector and property-preserving control from that ruling; if unresolved, report this conjunct `not_established`, without inventing a new population guarantee. Keep the all-unresolved baseline, risk–coverage, anti-degeneration, OPS-R7 version/interference/repeated-look cases, and sealed-oracle refusal.

### RGY-04 — GYD-09 positive update contradicts the current WP-01/WP-02 non-effect

- **Severity:** High
- **Bucket:** New class — future capability acceptance bypasses an active computation prohibition.
- **Task:** GYD-09.
- **Exact anchors:** `gy_learning-proposal.json#/task_solutions/1/acceptance_discriminators/0` and `/migration_and_rollback`; the task itself records `WP-01/02 withheld` (`tasks.json:2368–2389`). The governing non-effect and activation predicates are `withheld-propositions-register.md:127–161`; original O1 is `GY-engine-subordination.md:5439–5465`.
- **Counterexample:** AS2 and W5-K03 pass, so the proposal’s positive path writes an immutable posterior, while WP-01’s live SMDV-1 producer/content-bound comparison/W4-K02 provenance activation is still absent. The governing register says no posterior may be mutated today. WP-02 separately says no routine `expected_variation` schedule exists or may be inferred. C02 permits Bayesian inference as a supported profile; it does not authorize mutation or overrule these withheld predicates.
- **Minimal coherent fix:** Keep the Bayesian updater as the required O1 profile and keep candidate diagnostics/typed freeze work buildable, but add the exact WP-01 activation as a prerequisite for any `prediction_error` posterior mutation. Keep `expected_variation` behind WP-02’s separate principal ruling and predeclared schedule. GYD-09 can be technically prepared without claiming either activation; its positive acceptance must not fire before the applicable door is activated.

### RGY-05 — Clarify the optional O2→O1-confirmed hypothesis input to O3

- **Severity:** Medium
- **Bucket:** New class — original admissible input path may be narrowed at the bridge.
- **Task:** GYD-12.
- **Exact anchors:** `gy_learning-proposal.json#/task_solutions/4/preferred_solution`, `/implementation_steps/0`, and `/composition_contracts/0` define O3’s input as an O1 “effect-update” ref; GYD-09 limits its posterior update to a predeclared `prediction_error`. Original O3 explicitly allows “a confirmed effect (O1) or a confirmation-promoted hypothesis (O2 → O1)” (`GY-engine-subordination.md:5475–5481`). The R12 workstream correctly says O3 depends on O1+AS3, not O2, and UI-08/DS21 is downstream (`workstreams/03-gy.md:7,30`).
- **Counterexample:** An O2 candidate is admitted to the canonical ledger, then the confirmatory O1 route validates it, but it is not a predeclared-effect posterior. If the O3 bridge accepts only the GYD-09 posterior artifact, this source-permitted O1-confirmed hypothesis can never reach O3; alternatively, making GYD-12 depend on O2 completion would violate the R12 dependency ruling.
- **Minimal coherent fix:** State that O3 may consume an O1-confirmed effect update or an O2-origin hypothesis only after the same O1 confirmation firewall, preserving origin/profile/provenance. Keep O2 optional: no O2 start/completion dependency, no direct O2 world write, and no DS21 prerequisite. If the accepted integrated scope intentionally excludes the optional hypothesis route, record that precise source-qualified disposition rather than silently narrowing the original source.

### RGY-06 — O3 branch/event/WMR multi-object recovery is unspecified

- **Severity:** Medium
- **Bucket:** New class — cross-artifact commit outcome.
- **Task:** GYD-12.
- **Exact anchors:** `gy_learning-proposal.json#/task_solutions/4/reuse_anchors` names separate event/fact persistence, branch/head updates and WMR persistence; `/implementation_steps/1` says to create the branch/event and append the WMR, with stale-head refusal. The shared S02 decision says to use a native transaction only if it spans all local effects, otherwise use durable intent/reconciliation and a safe unknown-outcome state (`solutions/00-shared-decisions.md:15–19`).
- **Counterexample:** The event/branch head advances and WMR persistence fails, or WMR bytes persist while the conditional branch-head update loses a race. A stale-head check alone does not settle either partial outcome; the proposal does not establish whether the existing owner provides one transaction across both artifacts or a recovery protocol.
- **Minimal coherent fix:** At accepted-source rebind, establish the actual transaction boundary. If it covers the event, branch head and WMR together, bind the commit to that transaction and read it back. Otherwise use the existing owner’s durable intent/reconcile path with stable operation identity and an explicit unknown-outcome refusal until reconciliation. Do not infer multi-object atomicity from one branch-head CAS, and do not add a new global coordinator.

## Complete 26-task scope

“None” means no separate material red-team finding in this pass, not task acceptance or implementation evidence. RGY-02 is a shared classification finding, so instances below do not trigger separate repairs.

| Task | Review result |
|---|---|
| GYD-01 | RGY-01 |
| GYD-02 | RGY-02 instance |
| GYD-03 | None; retain real D0/context and native intake requirements |
| GYD-04 | None; exact denominator and adjudicator remain required evidence, not an accuracy claim from a witness |
| GYD-05 | None; source, scope/time and competent ruling are kept distinct |
| GYD-06 | RGY-02 instance; retain `a_spec_gap` and do not count fixtures |
| GYD-07 | RGY-02 instance; keep current-family GX and routed-red acceptance |
| GYD-08 | RGY-03 |
| GYD-09 | RGY-04; Bayesian O1 retained |
| GYD-10 | None; proposal qualifies online-FDR assumptions and leaves uncontrolled signals non-authoritative |
| GYD-11 | None; preserves 24 packets, five individually failing mutations, adjacent valid controls, and real consumer |
| GYD-12 | RGY-02, RGY-05, RGY-06 |
| GYD-13 | RGY-02 instance; the actual operator event can remain external, the instrument/corpus/store receipt are local chain artifacts |
| GYD-14 | None; source bytes and any real trust/legal/accessibility evidence remain distinct from candidate rendition comparison |
| GYD-15 | RGY-02 instance; implement cutoff/receipt chain internally, reserve external slots for actual trust/source facts |
| GYD-23 | None; retains measurement-rooted Estimate-only terminal and original budget/registry rules |
| GYD-24 | None; retains all 16 facets, named connectors and exact costed acquisition exit |
| GYD-25 | RGY-02 instance; freshness derivation is a local owner/consumer property |
| GYD-26 | RGY-02 instance; actual judge output and consumer contract are local outputs/contracts |
| GYD-27 | None; real event linkage and Ring-2 provenance are preserved |
| GYD-28 | None; digest integrity remains separate from artifact-specific authority |
| GYD-29 | None; complete current set, temporal roles and P37 classifications remain required |
| GYD-30 | RGY-02 instance; actual callers/results/fresh consumers are internal acceptance outputs |
| GYD-31 | RGY-02 instance; consumer behavior is implementation proof, not an external input |
| GYD-32 | None; conforming resources remain discoverable with zero new central code; true new semantics still need typed extension |
| GYD-33 | RGY-02 instance; source evidence may be external, accepted consumer contracts are local work |

## Ratified constraints and source assurance

The substantive reading of adopted decisions is otherwise preserved: B01’s competing/set-valued causal completions and claim-type grounds; C01’s exact joint witness only for the concrete joint property it proves (never pairwise/marginal substitution); C02’s inference plurality with guarantees kept distinct; S0-K14’s independence only where independent correctness is claimed. In particular, GYD-30 and GYD-12 correctly reject a joint claim from marginals, GYD-09 keeps Bayesian O1 rather than replacing it with plurality, and GYD-01/09 keep causal grounds separate from mandate or authority. GYD-32’s zero-central-code claim is correctly bounded to resources already conforming to an existing semantic/protocol class.

Primary-web spot-checks support the proposals’ narrow external claims: [Dwork et al., adaptive analysis and holdout reuse](https://papers.nips.cc/paper/5993-generalization-in-adaptive-data-analysis-and-holdout-reuse.pdf) warns that adaptive feedback can overfit and describes a restricted reusable-holdout method; it does not make a local seal/hash a privacy mechanism. [Howard et al., confidence sequences](https://www.imstat.org/publications/aos/aos_49_2/aos_49_2.pdf) establishes time-uniform coverage under its stated stochastic assumptions, not validity under adaptive holdout selection. [SAFFRON](https://proceedings.mlr.press/v80/ramdas18a.html) requires valid sequential null p-values (the paper states conditional super-uniformity); [e-LOND](https://proceedings.mlr.press/v238/xu24a.html) permits arbitrary dependence only when input e-values meet validity conditions. The [AAAI transportability paper](https://ojs.aaai.org/index.php/AAAI/article/view/7861) requires source/target assumptions expressed by selection diagrams. [TUF 1.0.36](https://theupdateframework.github.io/specification/v1.0.36/) and [MLflow version/alias documentation](https://mlflow.org/docs/latest/ml/model-registry/workflow/) support only the narrow immutable-version/readback analogy used here; neither establishes atomicity or correctness of PolicyOS branch/event/WMR writes.

These sources support external method statements only; they do not prove local p/e-value validity, AS2 blindness, posterior calibration, producer completeness, an E02-bound bridge, or multi-store transaction behavior. This pass used bounded document reads and primary-web source pages only. No tests, builds, repository imports, installs, production-data reads, Git mutations, or tracked-file writes were performed. The ignored scratch output is the only file written by this review.
