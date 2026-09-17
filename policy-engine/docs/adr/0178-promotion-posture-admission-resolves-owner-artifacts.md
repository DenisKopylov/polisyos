# ADR-0178: Promotion admits the S6, S7 and S8 postures only from owner artifacts it resolves and recomputes

## Status

Accepted

## Date

2026-09-17

## Decision record

Taken by the principal on 2026-09-17, on the architect's design pass of the same day. It is recorded in the form required by the identity decision's §9 item 7. The question, options, premises, remainder and revisit triggers below are part of the decision, not commentary on it.

## Context

Register row `promotion-s6-s7-s8-injected-posture-admission-mapping` recorded that the S6, S7 and S8 promotion evaluators accept posture flags without resolving the evidence behind them. The falsifier `test_injected_posture_flags_are_a_bounded_predicate_not_evidence_admission` passes invented references and favourable flags, and the evaluators are locally satisfied. On 2026-09-17 the principal accepted the direction and asked for a deeper design before deciding. The design pass measured the following at `main` `57282201d`.

1. **N9 takes three flat DTOs from its context.** They are `Layer2S6BlindSpotPostureInput`, `Layer2S7DelegationPostureInput` and `Layer2S8ValuePostureInput` (`pdc/_impl/layer2_design_search.py`), and they feed three obligation classes:
   - IMPLEMENTATION, via S6;
   - NORMATIVE, via S7, with a condition on S6;
   - part of VALUE, via S8 together with N8.

   No production path supplies them. The promotion-conjunction lane's census counted 0 producer call sites over 2,664 `src/` Python files; that census was executed by the lane and not re-run here. The architect's own search for the context keys also found none. With the postures absent, all three obligations return `scope_insufficient` in production.
2. **The runner already refuses a context-supplied gate predicate.** `run_canonical_promotion_sequence` raises `promotion_context_cannot_supply_gate_predicate` for `open_world_gate` and the legacy predicates. The S6, S7 and S8 flags are the same kind of input, and the guard does not cover them.
3. **S6 has a real producer.** `build_s6_blind_spot_firewall_report` in `runtime/quality/design_axes/blind_spot_firewalls.py` runs five axis evaluators with the named firewalls P18, P19, P21, P22 and P24. However:
   - the report is not persisted to CAS;
   - its own authority boundary lists `production_claim_authority` and `rollout_authority` under `may_not_use_for` — it is a firewall ("no blind spot fired"), not a positive adequacy claim;
   - the rows it evaluates are supplied by the caller: construct measurability status, mandate-source dispositions and the rest;
   - N9's S6 evaluator fails only on `blocked`, so `limited` satisfies it, while S7 requires `clear_fail_closed`.
4. **S7's eligibility flag has no production producer.**
   - `evaluate_delegation_for_case` in `design_axes/mandate_bounded_delegation.py` takes `governed_pilot_eligible` from the corpus gold label `expected_governed_pilot_eligible`. It is a benchmark harness.
   - The `HumanDecisionRecord` v2 already binds a reviewer separation, a presentation contract, an exposure session, the digests of the exposure artifacts, nine predicate receipts and a validity window.
   - `HumanDecisionService` re-resolves signed production approvals through `resolve_production_approval_inputs`.
   - The record's source kinds are only `agent_action_authority` and `production_approval`.
5. **S8 has a real owner.** `NormativeValueScheduleOwner` (`design_axes/value_choice_provenance.py`) verifies separate signers and re-resolves scope, frontier, generation and TTL before emission. However:
   - N9's S8 DTO takes its disposition and its P20 and P22 statuses as supplied values;
   - the owner's mandate check `_require_mandate_pass` takes the S6 mandate disposition as a string.
6. **The promotion-safety acceptance slot already exists.** `PromotionSafetyAcceptanceSlot` in `runtime/quality/promotion_safety.py` was split and decided on 2026-09-17 in `eval-safety-promotion-authority-producer-missing`.

**The question.** What must N9 accept as the S6, S7 and S8 postures, what independently verified evidence satisfies each predicate for a protected promotion, and in what order do they compose with the promotion-safety acceptance?

## Options considered

| option | what it does | cost, and who pays | disposition |
| --- | --- | --- | --- |
| **A. Resolve and recompute, with graded independence** | N9 accepts only references to owner-persisted artifacts, resolves them through their owners, recomputes the predicates, and checks that the evidence behind each input row is independent of the candidate at a declared level | Engineering, paid by `team-runtime`: three resolvers, S6 persistence, a new S7 source kind, a binding check in N9. Candidate authors pay in more evidence work and more honest refusals. The principal owns one institutional slot | **taken** |
| B. Signed posture admission summaries (SLSA VSA shape) | a verifier signs a pass/fail summary with the policy and input digests, and N9 trusts the summary | Less recomputation, but a new trust root. A summary does not protect against a compromised verifier | not taken as authority; permitted later as a cache over A |
| C. One S7 human decision attests S6 and S8 | a signed approval stands in for the other two postures | Cheapest. It substitutes a signature for established evidence (`W5-K08`), repeats the delegated self-certification failure, and is the false clear S8 already counts as `s7_decision_substitution` | refused |
| D. Sign the existing flags | flags become signed flags | The same channel asserts and confirms the evidence (`W5-K08`) | refused |
| E. Only extend the context guard | the three obligations stay `scope_insufficient` | Cheapest and honest, but a governed promotion stays impossible indefinitely, which identity decision §9 item 5 rejects as a scheduling posture | adopted only as step 0 of A |

## Decision

### D1 — N9's input contract

- **The guard grows.** The runner's context guard extends to `s6_blind_spot_posture`, `s7_delegation_posture` and `s8_value_posture`; supplying any of them is refused as `promotion_context_cannot_supply_posture_predicate`.
- **References replace flags.** N9 takes content-addressed references to owner-persisted admissions and derives the three obligations by resolving and recomputing them.
- **The DTOs become projections.** The three flat DTOs remain only as projections written into the receipt's owner projection — outputs, never inputs.
- **The falsifier inverts.** Injected flags must now yield a refusal on the N9 path.

### D2 — S6

1. **Persist, then recompute.** The S6 firewall report is persisted to CAS by its owner. N9 recomputes `overall_posture` from the five persisted axis records; a mismatch is a failure.
2. **In the protected modes the obligation requires `clear_fail_closed`.** The protected modes are `sandbox_pilot`, `field_pilot` and `deployment`. Outside them, `limited` remains satisfied with its limitations carried. This removes the conflict with S7.
3. **Independence levels.** Every input row of the five axis evaluators carries provenance to an owner artifact at a declared level:
   - **L0** — recomputed by N9 from persisted inputs;
   - **L1** — produced by a producer whose identity (its import closure, compute-economics gate E12) differs from the candidate generator's;
   - **L2** — signed by a principal with recorded separation from the candidate's operator;
   - **L3** — an external institution, as a typed and empty slot until appointed.
4. **Rows below the required level are downgraded.** A row with no provenance, or produced by the candidate's own producer, is treated as unestablished, so its axis cannot `pass`. The level each axis requires in each protected mode is parameterised. For the mandate and aggregation rows it is set when `CV-DR1` and `CV-DR4` report (see D6).
5. **The S6 report is necessary, not sufficient.** It shows that no named blind spot fired. It is never read as scientific adequacy, as its own authority boundary says.

### D3 — S7: a new decision source, not a narrowing of production approval

1. **A new source kind.** `HumanDecisionRecordSourceKind` gains `governed_pilot_eligibility`, and it is a new kind, not a narrowing of `production_approval`. The decision is different (a bounded pilot with stop conditions, not a production deployment), its basis is different, and its validity differs. Neither substitutes for the other, in either direction.
2. **A signed basis manifest.** Working name `GovernedPilotEligibilityBasis`. It binds:
   - the candidate content hash and the design-problem binding;
   - the protected mode;
   - the digests of the S6 and S8 admissions;
   - the digest of the promotion-safety acceptance, or its typed-empty state;
   - the mandate record, the decision class and the required role;
   - the pilot's stop and rollback conditions;
   - the validity window.
3. **A resolver.** `resolve_governed_pilot_eligibility_inputs`, modelled on `resolve_production_approval_inputs`. It re-resolves the signed inputs, recomputes the bindings, intersects the validity windows and checks the reservation generation.
4. **What the decider saw, and who decided.** The record is valid only if:
   - its exposure-artifact digests include the basis digests — what was shown is what was decided;
   - it carries evidence of reviewer separation.

   A self-review cannot satisfy S7.
5. **The flag is derived.** `governed_pilot_eligible` is true exactly when the resolver passes. `evaluate_delegation_for_case` stays a benchmark harness and is marked as not a production source.
6. **Who may decide in a protected mode** is a typed and empty institutional slot. The mechanism is demonstrable with a fixture principal carrying a behavioural-fixture badge.

### D4 — S8

1. **Derived from the owner.** The S8 predicate is derived from `NormativeValueScheduleOwner.project` and the owner's generation disposition for the candidate's frontier and generation. A candidate outside the authorised frontier of its generation is not established.
2. **A digest, not a string.** The S8 admission binds the S6 mandate record by digest, replacing the string disposition passed to `_require_mandate_pass`.
3. **Dispositions that fail in the protected modes:** `contested_multi_principal`, `advisory_only` and `shadow_scenario_only`. Recorded dissent stays in the projection.
4. **No new owner is created.** This is wiring plus an admission policy.

### D5 — Composition

The postures form an acyclic chain:

> S6 admission → S8 admission → promotion-safety acceptance → S7 decision

The human decides last, over digests of everything upstream. The safety acceptance does not bind S7, so there is no cycle.

**The binding check.** N9 resolves each admission independently and refuses `posture_binding_drift` when a digest in the S7 basis differs from the admission it resolved.

### D6 — Staging against the correspondence decision research

The acceptance rules for four input rows are exactly the questions of backlog Group E:

| input row | question |
| --- | --- |
| the S6 mandate row | `CV-Q1` |
| the normative part of S8 | `CV-Q2` |
| the S6 aggregation row | `CV-Q4` |
| S7's right and grant | `CV-Q5` |

The admission architecture (D1–D5) is built now. Those rows' required independence levels stay parameters until the `CV-DR` final packages are decided, and are then set by dated record.

## Premises

Each premise, if it fails, reopens this decision.

1. **The measured facts in *Context* hold at the implementing commit.** A lane re-measures them before building, under register rule 9.
2. **Owner re-resolution is affordable inside N9.** `HumanDecisionService` and `NormativeValueScheduleOwner` already re-resolve per call.
3. **Import-closure identity is a usable proxy for "a different producer".**
4. **Precedents from other fields apply by structure,** not by domain:
   - admission that checks attestation content rather than labels;
   - independence graded by criticality;
   - validation performed before use approval;
   - approval bound to the exact content shown;
   - pilot approval kept distinct from market or production approval.

   See *External precedents*.

## Consequences

**Positive.**
- A governed promotion becomes reachable through evidence rather than assertion.
- Every refusal names the missing artifact or level.
- The CV decision research lands in named slots instead of in prose.

**Negative, and accepted.**
- In the protected modes, S6 will often be `limited` until independent producers exist for capacity feasibility and strategic response. A first field-pilot promotion then stays blocked on IMPLEMENTATION — visibly, and correctly.
- More evidence is required of every candidate.
- The S7 schema literal grows. The change is additive, and historical v1 serialisation is unaffected.

## What this does not decide

- The scientific acceptance criteria for proxy validity and strategic response.
- Who may decide S7 in a protected mode.
- The open `sandbox_pilot` authority question in `eval-safety-promotion-authority-producer-missing`.
- Semantics outside the protected modes, apart from carrying `limited` as a limitation.

## Revisit triggers

- Recomputation inside N9 proves too costly. Then add option B's summaries as a cache, never as authority.
- An S7 decider cannot practically review the exposed bundle. Then redesign the presentation contract; do not loosen the binding.
- Import-closure identity proves too coarse to separate producers. Then switch to component and signer identity.
- `CV-DR1` recommends an external legal determination. Then the S6 mandate row moves to L3.
- `limited` blocks every realistic protected pilot while no producer work is progressing. Then the principal decides explicitly whether `sandbox_pilot` may accept a disclosed `limited`. It is never relaxed silently.

## Concrete impact

- `src/polisyos/runtime/quality/promotion_sequence.py`:
  - the context guard (D1);
  - posture resolution and derivation of the three obligations;
  - the `posture_binding_drift` check (D5).
- `src/polisyos/pdc/_impl/layer2_design_search.py` — the three evaluators become projections over resolved admissions; the S6 rule for protected modes (D2.2).
- `src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py` — persistence of the S6 report and row provenance levels (D2).
- `src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py` — the new source kind; the harness marked non-production (D3).
- `src/polisyos/runtime/http/services/human_decisions.py` — the basis manifest and `resolve_governed_pilot_eligibility_inputs` (D3).
- `src/polisyos/runtime/quality/design_axes/value_choice_provenance.py` — the mandate bound by digest, and the admission projection (D4).
- `src/polisyos/runtime/quality/promotion_safety.py` — the acceptance digest consumed by the S7 basis (D5).
- `tests/unit/runtime/quality/test_promotion_sequence.py` — the injected-flag falsifier inverts (D1).
- Register rows `promotion-s6-s7-s8-injected-posture-admission-mapping`, `eval-safety-promotion-authority-producer-missing` and `first-promotion-candidate-with-complete-evidence` carry this decision by dated append.

Working names may be changed by the implementing lane with a dated record.

## External precedents

Cited for their structure, not their domain.

- **SLSA Verification Summary Attestation** — verifiers record the policy and input digests; a summary does not protect against a compromised verifier. <https://slsa.dev/spec/v1.1/verification_summary>
- **Kyverno** — admission evaluates conditions on signed attestation content, not labels. <https://kyverno.io/docs/policy-types/cluster-policy/verify-images/overview/>
- **Wirecard / EY** — confirmations routed through the same channel that asserted the balances. <https://www.cityam.com/ey-failed-to-request-wirecard-bank-statements-for-three-years/>
- **FAA certification of the Boeing 737 MAX** — weaknesses in delegation and oversight. <https://www.oig.dot.gov/sites/default/files/FAA%20Certification%20of%20737%20MAX%20Boeing%20II%20Final%20Report%5E2-23-2021.pdf>
- **ISO 26262 confirmation measures** — independence graded by criticality. <https://iso26262.academy/features/concepts/confirmation-measures>
- **Federal Reserve SR 11-7** — validation independent of development and use, and effective challenge. <https://www.modelop.com/ai-governance/ai-regulations-standards/sr-11-7>
- **HM Treasury AQuA Book** — the roles of analyst, assurer and approver kept distinct. <https://best-practice-and-impact.github.io/aqua_book_revision/intro.html>
- **What You See Is What You Sign** — approval bound to the displayed content. <https://en.wikipedia.org/wiki/WYSIWYS>
- **45 CFR 46** — IRB approval of the specific research before it starts. <https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-A/part-46>
- **EU AI Act Article 58** — sandbox testing terms and safeguards agreed per test. <https://artificialintelligenceact.eu/article/58/>
- **Assurance 2.0** (Bloomfield and Rushby) and **multi-legged arguments** (Bloomfield and Littlewood, DSN 2003) — defeaters recorded explicitly, and confidence from diverse, independent legs. <https://arxiv.org/html/2604.00034>, <https://ieeexplore.ieee.org/document/1209913/>

## Related Decisions

- Binds under `W5-K08` (a signature may not stand in for an established correspondence), identity decision §9 items 5–7, and `S0-K06`'s band split.
- Composes with the 2026-09-17 promotion-safety decision recorded in register row `eval-safety-promotion-authority-producer-missing`.
- Related: ADR-0176, ADR-0177.

## Amendment — 2026-09-17: D2.3 and D6 reopened by the CV-DR findings

This section amends the decision above by dated record. D2.3 and D6 stand above as the record of what was decided earlier the same day; where they conflict with this section, this section governs.

### What reopened it

The CV-DR decision research, published at `docs/research/policy-operations/cv-dr-decisions/` and decided in ADR-0179, was written without sight of this ADR. Three of its accepted findings meet D2.3 and D6 head on:

1. **`AUD-DR-X-003`, cross-question, and `RT-DR1-002`.** Independence offers no common truth-producing shortcut. It consists in reaching evidence capable of refuting the premise; separate files, organisations, signatures or reviewers do not give it. Even a non-producer may be shown only producer-curated material. D2.3's generic levels L1 (a different import closure) and L2 (a separated signer) are exactly such separation, so as pass conditions they would admit a curated row. Premise 3 of this ADR — that import-closure identity is a usable proxy for independence — fails.
2. **D6 expected the research to set levels for four rows.** The research refuses a common level scheme: each premise names its own refutation-capable evidence.
3. **`RT-DR-X-002`.** Proxy-strict refusal is a defect as well. Controls against material substitution need paired property-preserving controls.

This is the revisit trigger this ADR named: *import-closure identity proves too coarse to separate producers*.

### Options

| option | disposition |
| --- | --- |
| Keep L0–L3 as pass conditions and only document the finding | not taken — it admits curated rows the research showed unsafe |
| Drop independence requirements for S6 rows | not taken — it reopens the self-certification this ADR exists to close |
| **Require, per row, named refutation-capable evidence the admission verifier can reach; keep producer and signer separation as hygiene, necessary where it applies but never sufficient** | **taken** |

### Revised D2.3 — row evidence

1. **Named refutation-capable evidence.** Every input row of the five S6 axis evaluators names the evidence capable of showing its declared status false, and that evidence must be reachable by the admission verifier, not only supplied by the row's producer. Illustrations, not a closed list:
   - measurability — the data-plane binding and availability record that could show a construct unobserved;
   - aggregation — the bound target of ADR-0179 `CV-Q4`, which could show a claim-scope mismatch;
   - capacity feasibility — capacity data that could show the dimension infeasible;
   - mandate — the accepted legal source and the lever's actual behaviour under ADR-0179 `CV-Q1`;
   - strategic response — response-channel evidence.
2. **An unnamed or unreachable row is unestablished.** Such a row cannot pass its axis. The reason names the missing evidence.
3. **Separation is hygiene.** A different producer identity, whether by component, signer or import closure, remains required where the row's evidence is produced, but it is never itself a pass condition.
4. **Recomputation stays.** L0 — N9 recomputing what persisted inputs determine — stays as it was.
5. **No common label.** No common provenance label or level is introduced; `P37` provenance classes are unchanged.

### Revised D6 — rows that depend on the CV decisions

The four rows take their evidence requirement from the accepted principles of ADR-0179, not from a common level:

| row | principle it follows |
| --- | --- |
| S6 mandate row | the `CV-Q1` principle |
| normative part of S8 | the `CV-Q2` principle |
| S6 aggregation row | the `CV-Q4` principle |
| S7 right and grant | the `CV-Q5` principle, with native reuse of `execute_bound_effect` as the presumption |

Where a principle's first profile is still open (ADR-0179), the dependent row is unestablished in the protected modes, with the missing profile named. The admission machinery is built user-neutrally now, and candidate and demonstration paths remain buildable.

### New D7 — paired controls

Every refusal path this ADR creates — `posture_binding_drift`, S6 recompute mismatch, S7 exposure-digest mismatch, and the context guard — is tested with at least one material substitution that must refuse. It is also tested with at least one property-preserving change that must not:
- canonical re-serialisation;
- a display alias;
- a clerical protocol edit that keeps the approved content;
- the same target with a different estimator.

Refusals carry reasons.

### Revisit triggers added

- A row passes on separation alone, without named reachable evidence.
- A property-preserving change is refused.
- Adding a new user's evidence source requires changing the admission mechanism rather than supplying a profile or configuration — the principal's growth ruling of 2026-09-17, recorded in ADR-0179.
