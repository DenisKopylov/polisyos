---
title: INT-R9 — Proving the First Positive Governed Promotion Without Cherry-Picking
status: delivered
kind: deep-research
research_task: INT-R9
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r9-amendment
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
amended_after_audit: research/int-r9-independent-audit@a09128e6b914292597054b82bda2701d541b1fea
bound_int_r10_commit: research/int-r10-family-wise-risk-composition@317fc9c36e710ac75634096c4d14a714b8bff504
bound_int_r1_amendment_commit: research/int-r1-amendment@66baff37c7f566fc770377ba6c66a8dc7b517ce0
amendment_choice: option_b_keep_adaptive_repair_withdraw_numeric_family_claim
authoritative_for:
  - research-level anti-selection and custody protocol for a finite first-promotion attempt sequence
  - bounded interpretation of what the earliest qualifying governed attempt could and could not establish
  - repository-grounded contamination disposition of the current proving-ground corpus
  - research-level requirements for negative-result publication, sealed evaluation, adjacent-case transfer, falsification, adjudication, and correction
  - explicit withdrawal of every sequence-level numeric false-promotion claim for the adaptive protocol
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - canonical schema or package placement
  - canonical owner assignment
  - authority grant
  - capability claim
  - promise that a positive promotion is achievable
  - benchmark passage
  - legal compliance conclusion
  - institutional competence conclusion
  - production readiness
  - a claim that three distinct problem scopes share one delta budget
  - a claim that P(false first promotion) is bounded by delta or by 3 times delta for this adaptive protocol
  - a claim that cross-scope cap enforcement or a family projection exists at the pinned baseline
  - a numeric claim based on INT-R10 Theorem B before independent audit and canonical implementation
  - creation of a parallel status lattice
  - creation of a second confidence ledger
  - creation of a second oracle-independence framework
research_only: true
---

# INT-R9 — Proving the First Positive Governed Promotion Without Cherry-Picking

## Executive Finding

**Result: `accepted_narrow_scope`, amended after independent audit. Current execution readiness: `blocked`.**

The accepted result is a **prospective anti-selection and custody protocol without a sequence-level risk number**. PolicyOS may govern which attempt is first, what was fixed before result-bearing access, which failed and disputed attempts remain in history, whether a case or run was substituted, how independent human adjudication is evidenced, and how every terminal is published. Under the current three-slot adaptive sequence it may not assert `P(false first promotion) <= delta`.

The independent audit found the original report's blocking error. N9 derives one confidence scope per design-problem binding (`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`); the confidence ledger's root, ordinal, prior spend, and Basel-square allocation are local to that scope (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:156-184`, `:518-557`, `:1301-1364`, `:3890-4025`). Three fresh cases therefore create three distinct canonical scopes. Prose saying “cumulative” cannot make those scopes one family.

INT-R10 subsequently established the robust result used by this amendment. For a prospectively fixed family, valid local bounds `b_i`, fixed and enforced before member execution, compose by **Boole's inequality** when `sum_i b_i <= delta_F`. No common null, common estimand, exchangeability, or independence is needed. The pinned repository implements neither pre-execution cross-scope caps nor a family projection, so no family bound is currently derivable at all.

> **Correction (2026-08-03, architect, after the INT-R10 independent audit).** An earlier draft of this paragraph reported INT-R10's original corollary — that the composition is *sharp* at `3 * delta`, giving `3/100` at the live registry. **That corollary was refuted by the INT-R10 audit and withdrawn in the INT-R10 revision.** It treated a scope's *root budget* as risk a member event can attain, whereas the owner's Basel-square kernel reserves `alpha_t = delta * expanded_class_weight * schedule_mass * (6/pi^2) / (t+1)^2` and the coefficient makes that series telescope: the pathwise envelope over any adaptive class sequence in one scope is strictly below `delta * (3/20) * mass`, the maximum expanded per-class weight being `3/20` on `calibration`. Three scopes therefore sit below `(9/20) * delta` — **below a single `delta`**, not at `3 * delta`. The disjoint-event sharpness result survives only in the abstract, after deliberately coarsening the local owner to `P(V_i) <= delta`.
>
> **Nothing in this protocol depended on the withdrawn figure.** Option B attaches no probability to the first-positive event, so the correction is a factual repair to a description of a sibling result, not a change to any INT-R9 claim. The current binding is `research/int-r10-revision` (superseding `research/int-r10-family-wise-risk-composition@317fc9c36`); see `docs/research/policy-operations/int-r10/revision-ledger.md`.

This amendment chooses **Option B** from the audit's R1/R2 specification:

> Keep result-bearing implementation repair between slots, classify the sequence honestly as adaptive continuation, and withdraw every numeric family-wise claim.

That choice has a real cost. Chronology, anti-substitution, sealing, adjudication, falsification, and bounded publication remain governed, but no `delta`, `3 * delta`, or other probability is attached to the event that the reported first positive is false. Each confidence receipt remains local, conditional, and owned by the canonical ledger. INT-R10 Theorem B is audit-pending and is used only to mark why outcome-dependent repair needs a selection-valid owner theorem; no numeric claim in INT-R9 relies on it.

The strongest permitted positive statement is procedural:

> The earliest qualifying attempt in the prospectively committed sequence was evaluated under the named implementation revision, environment, case-selection rule, sealed primary and adjacent packages, existing canonical owner gates, evaluator version, adjudicator identities, maintained assumptions, protocol version, and complete prior-attempt record; no prohibited post-result case, order, run, criterion, threshold, reviewer, exclusion, or firstness substitution was found in the governed record.

That is a custody claim, not proof against covert collusion, fabricated records, every semantic shortcut, upstream pool-selection bias, omitted obligations, or evaluator error. It is not population performance, legal compliance, institutional competence, production readiness, or family-risk control.

The current repository cannot execute even this bounded protocol. All 13 real proving-ground cases and both synthetic adjudications are public answer-bearing regression material. No sealed decisive or adjacent unseen case exists. Existing reviewer identifiers are role placeholders, not accountable independent natural persons. S0-GAP-02 remains the commissioned canonical oracle/evaluator-custody work. The amended INT-R1 says `bounded_complete` is not issuable at the pinned baseline and the current coverage standing is `open_world_unresolved`; that blocks the affected protected action.

`ua-msme-affordable-loans-2022` remains ineligible as decisive primary **and** adjacent evidence. It is the only full-loop case, appears in development evidence, exposes its expected answer, and is named by the current N9 input default. Exclusion may make the protocol end in `exhausted_without_promotion`. That is a valid primary result.

Supporting artifacts are:

- [contamination census](int-r9/contamination-census.md);
- [state machine and artifact sketches](int-r9/state-machine-and-artifact-contracts.md);
- [fixture and falsifier specifications](int-r9/fixture-specifications.md);
- [post-audit amendment ledger](int-r9/amendment-ledger.md); and
- [retired structured artifact](int-r9/first-promotion-evaluation-protocol.yaml), now comments-only and parse-to-null rather than executable.

---

## 1. Task And Project Fit

### 1.1 Exact question and why research comes first

INT-R9 asks how PolicyOS can govern its first positive promotion without cherry-picking and without promising that a positive exists. The first positive is historically unique. Case choice, order, criteria, materiality, threshold references, implementation revision, source cutoff, run, retry, reviewer, exclusion, stopping, and public wording can all decide its meaning. A protocol written after result-bearing access cannot recover prospectivity.

The GY verification plan requires INT-R9 before a candidate is inspected and treats honest abstention or repair as legitimate outcomes (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2500-2575`). The constitution keeps B output shadow until canonical owners permit a bounded claim, reports but never targets `useful_design_rate`, and requires one status lattice (`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:145-230`).

The false production claims prevented are:

1. a tractable or already-known case was called an unseen test;
2. a favorable run replaced earlier failures;
3. materiality or criteria changed after their direction was known;
4. friendly reviewers were called independent from declarations alone;
5. an obligation gap was rescued by narrowing the same scored claim;
6. three local scopes were described as one risk budget; or
7. one bounded event was projected as general capability.

### 1.2 Four-way boundary verdict

The ratified identity decision makes PolicyOS the epistemic custodian of policy justification, not the administrator, court, regulator, payment operator, or source of external authority (`policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:35-220`).

| Verdict | INT-R9 disposition |
| --- | --- |
| **OWN** | Custody of preregistration, selection and order, freezes, attempt chronology, deviations, adjudication, bounded public wording, negative publication, and correction of PolicyOS's own first-promotion claim. |
| **INTEGRATE** | Externally authored case facts and expectations; S0-GAP-02 custody; amended INT-R1 coverage envelope; canonical N9/N11 receipts; competent materiality and conflict evidence; named-human identity and relationship evidence. |
| **OBSERVE** | Funder, employer, network, incentive, access, challenge, and succession signals before they are verified and admitted. |
| **OUT_OF_SCOPE** | Administration, legal-effect adjudication, certification of institutional competence, guarantee of representativeness, guarantee of a positive result, or replacement of external authorities. |

### 1.3 Result classification

| Element | Classification |
| --- | --- |
| Union composition and sharpness | theorem reused from INT-R10; not re-proved here |
| No retroactive holdout; no promise of a positive; no proof against secret collusion | impossibility/limit statements |
| Prospective selection, sealing, no substitution, adjudication, publication, correction | governance protocol |
| Public regression plus fresh primary/adjacent packages; registered-report-style outcome neutrality | design patterns |
| Three slots, six pairs, three panel members, two alternates | replaceable engineering conveniences |
| Exact fields, IDs, serialization, package paths | unresolved; no canonical standing |

---

## 2. Current Repo Baseline

### 2.1 Pinned states

- historical Stage-0 baseline: `4813b49f6ce14e8debf3aaea096f0967d38d9768`;
- original research inspection baseline: `d152565dcc11cea457dacd61fadc6e15dc3ecc86`;
- amendment baseline: `978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d`;
- audit input: `research/int-r9-independent-audit@a09128e6b914292597054b82bda2701d541b1fea`;
- multiplicity input: `research/int-r10-family-wise-risk-composition@317fc9c36e710ac75634096c4d14a714b8bff504`;
- coverage input: `research/int-r1-amendment@66baff37c7f566fc770377ba6c66a8dc7b517ce0`.

Only the five INT-R9 research files and the new amendment ledger are changed by this pass.

### 2.2 Canonical primitives and capability standing

| Anchor | Verified standing | Amendment consequence |
| --- | --- | --- |
| `policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375` | one N11 risk scope is derived for one design problem | preserve per-problem identity; do not invent a parent scope |
| `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:156-184`, `:518-557`, `:723-752` | roots, heads, and receipts are scope-local | local receipts remain separate |
| `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1364`, `:3890-4025` | ordinal/spend and Basel-square allocation are inside one scope | no sequence ordinal or family spend is claimed |
| `policy-engine/architecture/production_quality/confidence_ledger.toml:1-18`, `:53-121` | live `delta=1/100`; relevant adaptive owner theorem unavailable | no family number; no numeric adaptive claim |
| `policy-engine/src/polisyos/runtime/quality/candidate_firewall.py:1-260` | B output cannot backfill protected owner evidence | preregistration cannot mint authority |
| `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:90-109` | S0-K13/K15/K16 require semantic predicates, memorization resistance, retained dissent/failures, and bounded passage | binding protocol constraints |
| `policy-engine/docs/research/policy-operations/consolidation/stage0/stage0-additional-research-register.md:75-210` | S0-GAP-02 owns generic oracle/evaluator custody | reuse only; replacement must be canonical supersession |
| `policy-engine/docs/reference/policy-design-case-failure-patterns.md:70-78` | P27/P28/P29/P33/P34 guard duplicate owners, authorial proof, witness-as-spec, and premature green | no self-authored family proof or post-result exclusion |
| `policy-engine/docs/system-design-decisions/policy-design-custody-time-model.md:58-151` | receipt, transaction visibility, verification, admission, and action time remain distinct | seal must be independently visible before inspection |

The constitution's current-state block says only ua-msme has run the full composed loop, the other 12 are per-slice, all 13 remain typed blockers, `useful_design_rate=0`, B remains shadow, and D3.8 is unbuilt (`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:382-398`).

### 2.3 Population and contamination

The outcome-corpus README names 13 real cases (`policy-engine/docs/research/universal-policy-design/outcome-corpus/README.md:1-48`). The adjudication README lists 15 manifests: those 13 plus two synthetic fixtures (`policy-engine/docs/research/universal-policy-design/outcome-corpus/adjudications/README.md:1-52`). All expose expected identifiers, labels, and reviewer votes. Some semantic-pass entries have `gold_card: null`; that does not restore secrecy.

The exact full-directory facts are:

```text
calibration_round_id:
  deep-pilot-round-1 = 4
  null = 11

topology_mode:
  deep_pilot_overlap = 4
  partial_disjoint = 11

authority_level:
  production = 5
  governed = 6
  research = 4
```

The detailed, re-anchored case ledger is in [contamination-census.md](int-r9/contamination-census.md).

### 2.4 The ua-msme horn

**Disposition:** ua-msme is permanently public regression by default and is excluded from decisive primary and adjacent roles. A fresh hidden label cannot erase integrated development history. Reopening would require extraordinary causal-isolation evidence defeating known case-conditioned engineering; the pinned tree supplies the opposite evidence.

**Cost:** the first decisive case must be new and may expose missing generality, refuse, dispute, or never converge. The project loses the easiest positive headline.

### 2.5 Reuse-first path

Consume the canonical N9/firewall/local confidence receipts; consume a current amended-INT-R1 envelope; reuse S0-GAP-02 for custody; record INT-R9 workflow facts as additive custody evidence; let existing closeout/currentness/Atlas owners project the result. Do not create a second promotion gate, risk ledger, time vocabulary, status lattice, or oracle service.

---

## 3. External Research Baseline

PolicyOS's first promotion is not a randomized trial, i.i.d. benchmark sample, or ordinary null-hypothesis rejection. External fields transfer procedures and warnings, not population or authority proof.

| Field | Transfers | Does not transfer |
| --- | --- | --- |
| adaptive data analysis / reusable holdouts | repeated answer access changes a test into development; fresh one-time packages matter | Dwork-style distributional generalization to heterogeneous policy cases |
| preregistration / SPIRIT / trial registries | dated versions, declared criteria, amendments, deviations, and prospectivity | registration alone as sealing or independence |
| Registered Reports | outcome-neutral plan acceptance and publication of null results | editorial acceptance as authority admission |
| researcher degrees of freedom | bind interpretations, exclusions, runs, reviewers, and stopping before direction is known | published false-positive rates as PolicyOS risk numbers |
| sequential design / anytime-valid inference | aggregate procedures need valid accounting and stopping inside the theorem | clinical boundaries or one filtration across different design problems |
| benchmark contamination | visible test sets are regression; fresh tests expose overfit | one adjacent case as a representative sample |
| inter-rater reliability | retain raw disagreement and use coefficients only diagnostically | agreement as correctness or independence |
| publication bias | result-independent publication makes suppression visible | elimination of informal prestige incentives |
| commitments / timestamping | binding, hiding, access custody, and proof of prior existence | semantic truth or human independence |

The original section 3 transfer discipline survives. Pocock, O'Brien-Fleming, and Howard et al. support the warning that repeated opportunities need a valid aggregate procedure; they do not supply a cross-problem family theorem. INT-R10 supplies the applicable event arithmetic.

FIPS 180-4 supports digest/change-detection properties. The statement that an unsalted digest of a predictable answer is not hiding follows from the commitment literature and the threat model, not FIPS alone. Binding and hiding remain distinct properties.

---

## 4. Result — Amended FirstPromotionEvaluationProtocol

### 4.1 Exact claim boundary

The protocol governs the earliest qualifying attempt in a prospectively committed finite order. It establishes only observable procedural conformity under named artifacts and assumptions. It makes **no sequence-level probability statement**.

A local confidence receipt may retain its canonical conditional meaning. INT-R9 neither adds local bounds nor composes them. Public records must not display “family delta,” “cumulative confidence,” “remaining family budget,” or equivalent numeric language unless a later canonical owner extension has been implemented and independently audited.

### 4.2 Case-pair pool and selection

Before implementation-side reveal:

1. ratify a `CaseSelectionSpecification` stating purpose, external-validity boundary, eligible frame, strata, inclusion/exclusion, adjacency, conflicts, randomness, and public limits;
2. have a case unit separated from implementation, criteria, thresholds, and outcome-contingent reward author a finite primary/adjacent pool and separate expectation packages;
3. commit all inputs, expectations, authorship, conflicts, eligibility decisions, and selection rules using S0-GAP-02 custody;
4. select and order the three slots by a predeclared non-discretionary procedure; and
5. retain unselected packages under a prospective retirement/disclosure rule—never as replacements.

This closes post-result selection **within the committed pool**. It does not prove the pool was free of upstream tractability judgment. If the frame is purposive, every public claim must say so. A random draw from a purposive pool is not a random draw from policy space.

### 4.3 Preregistration contents

The sealed record binds:

- protocol, repository, executable tree, build, dependencies, environment, model/prompt, configuration, evaluator, rule, and schema versions;
- case frame, commitments, selection receipt, order, stopping, no substitution, and amendment rules;
- every applicable existing owner predicate and threshold reference without redefinition;
- source-flip, obligation-removal, no-bespoke, adjacent-transfer, wrong-scope, and opaque-ID properties;
- prospective materiality decision specification;
- panel, alternates, authors, custodian, eligibility reviewers, conflicts, evidence, and residual declared relationships;
- result-independent publication, raw-vote, dissent, challenge, and correction rules;
- exact `authoritative_for` / `may_not_use_for`; and
- CTM ordering proving transaction visibility before first inspection.

A git commit controlled by implementers is not sufficient custody.

### 4.4 Attempt order, stopping, and adaptive repair

The selected queue contains three slots as a replaceable engineering choice.

1. Freeze the exact implementation/environment, run public regression, then reveal only the next slot.
2. Stop on a valid positive.
3. A refused, void, or negative result remains public and scored in chronology.
4. After a result-bearing terminal, implementation repair may occur before the next input reveal.
5. **Every result-informed change is classified as adaptive continuation.** The protocol no longer grants a privileged “general repair” label.
6. Before the next reveal, publish the prior failure information used, repair rationale, exact diff/asset changes, new freeze, and proof that no later sealed package was accessed.
7. The earlier slot is never rerun or rescored as the first attempt.
8. A material dispute halts the sequence.
9. If all slots terminate without promotion, publish `exhausted_without_promotion`.

A later positive is therefore a positive of a later prospectively frozen revision inside an adaptive development chronology. It is not a repeated look at one fixed implementation and carries no family-risk number.

### 4.5 Public regression and freeze

Before each reveal, the frozen revision runs the 13 real cases, 2 synthetic adjudications, public semantic mutations, known-groundable seeds, a contract-level positive control, and a visible anti-bespoke negative. These are regression and diagnostics, never decisive holdout evidence. Controls and synthetic fixtures never enter a real-promotion numerator.

The freeze covers source/generated source, build outputs, dependencies, container/environment, model/prompt, templates, flags, configuration, adapters, aliases, registries, bindings, evidence dictionaries, source/query cutoff, caches, evaluator executable, and seed policy. Any post-reveal change voids or disputes that slot.

### 4.6 Promotion predicates

A slot may promote only when all applicable canonical owner gates and all procedural predicates pass:

| Predicate | Observable requirement |
| --- | --- |
| prospectivity | independently visible seal and selection precede access |
| next slot | earliest unresolved committed slot; no omission/replacement |
| public regression | every predeclared visible predicate passes before reveal |
| canonical owners | N9, firewall, local confidence and every applicable evidence/grounding/value/delegation/evaluation owner permit the exact claim |
| amended INT-R1 | current envelope permits the exact protected action; current baseline does not |
| sealed primary | evaluator-correct behavior on the frozen primary package |
| adjacent transfer | same freeze reaches evaluator-correct behavior; positive is not required |
| no bespoke mechanism | provenance, equality receipts, semantic scans, opaque IDs, registries, and adjacent behavior find no heldout-case mechanism |
| source flip | same positive authority claim cannot survive loss of a predeclared material dependency |
| obligation removal | same positive cannot survive removal/unknown status of a predeclared material obligation |
| independent adjudication | named humans, evidence/disclosures, clean access, quorum, raw votes, dissent, and succession rules |
| prospective materiality | every promotion-critical materiality decision was sealed direction-blind or the slot is disputed |
| publication | every earlier terminal, deviation, dissent, and limitation is durably published |
| bounded claim | wording names revision, environment, cases, evaluator, protocol, assumptions, purposive-pool boundary, INT-R1 remainder, and no family number |

A fixture samples a semantic property; it does not define the property. Equivalent implementations are allowed.

### 4.7 Materiality decision right

Materiality is load-bearing for sources, obligations, deviations, dissent, challenges, and ambiguity. Before sealing, a consolidation-approved mapping must identify for each class:

- the competent existing owner or governed owner composition;
- the rule/evidence used;
- decision time and transaction evidence;
- conflict and recusal rules;
- tie/escalation rule; and
- effect of unknown or stale competence.

Expected-package materiality decisions are committed before output. If an unforeseen promotion-critical materiality question appears after its direction is known, or the named owner is unavailable/conflicted, the result is **disputed**. It cannot be classified favorable after the fact. Research appoints no new canonical owner; inability to map the right blocks sealing.

### 4.8 Independent adjudication: evidence, declarations, and residuals

A decisive adjudicator is an identified accountable natural person who signs the record. A model, agent, synthetic reviewer, or role ID cannot qualify. The panel and alternates are predeclared and separated from implementation, selected-case/answer authorship, criteria/threshold/materiality authorship, unauthorized answer custody, direct line management, contingent compensation, and prior scored-output access.

Independence cannot be computed from self-declaration alone.

**Corroborating evidence is required where obtainable:** identity; employment/contract and reporting lines; funding and compensation terms; git/artifact authorship; custody/access logs; case/criteria contributions; governance roles; recusal decisions; and signed conflict records.

**Declared residuals remain explicit:** informal friendship, professional networks, reputational stake, undisclosed future benefit, and covert collusion cannot generally be disproved. Same-funder, shared-governance, or closely aligned network relationships receive an explicit predeclared disposition—disqualifying, conditionally admissible with stated residual, or unresolved/disputed. They never auto-pass because three people signed `none_declared`.

Promotion requires the predeclared quorum, no dispute vote, no unresolved material dissent, and reasons for abstentions. Raw votes and disagreement remain public. Calibration on all 15 public manifests is development evidence, not proof of correctness or independence.

### 4.9 Sealing and S0-GAP-02

Input and expectation/evaluator packages remain separate. Expectation access occurs only after candidate output and execution records are frozen. Any credible leak voids/disputes the slot and preserves its chronology.

S0-GAP-02 owns canonical serialization, hiding/binding commitment, key/secret management, least privilege, access logs, dual-control reveal, rotation, succession, challenge, incident response, and generic evaluator/reviewer machinery. A replacement is acceptable only if an expressly governed decision **supersedes** S0-GAP-02 as the canonical owner. “Equivalent” never means a sibling INT-R9 service or schema.

### 4.10 Adjacent unseen case and no-case-specific-code

Each primary has a separately committed adjacent case sharing a declared mechanism/problem family and differing on at least two material context dimensions. The same binary/configuration/evaluator runs both. Correct adjacent behavior may be positive, limited, unknown, or refused. Requiring a second positive would target the forbidden metric.

No-case-specific evidence includes equality receipts for frozen assets; literal and semantic-fingerprint scans; source URL/alias/embedding/binding review; registry/adapter deltas; binding provenance and historical commits; opaque-ID mutation; same-freeze adjacent execution; maintainer declarations as nonsufficient evidence; and review of departed contributors. A direct or indirect heldout-case branch/binding is automatic NO-GO.

### 4.11 Source flip and obligation removal

The source flip changes one predeclared material dependency while preserving transport shape and unrelated facts. The same positive authority claim may not survive unchanged.

The obligation-removal falsifier removes, invalidates, or makes unknown one material obligation represented by the exact amended-INT-R1 interface. A positive under the same scope may not survive. One sampled obligation never proves open-world completeness.

Targets, materiality, acceptable semantic relations, and deciding owners are committed before inspection. Opaque variants prevent fixture-ID special cases.

### 4.12 Enforcement surface for the useful-rate ban

`useful_design_rate` may not affect case frame/pool/order, criteria, thresholds, materiality, fixtures, run/seed/retry/stopping, reviewers, compensation, publication, or promotion. Observable violations include easier-case substitution, hidden reruns, post-result threshold/materiality changes, failed-run exclusion, denominator edits, outcome-contingent rewards, and case-specific repair for a still-sealed heldout case.

INT-R9 does **not** define the metric denominator. It records whether a slot was selected, revealed/inspected, retired before inspection, void, refused, disputed, promoted, or unreached. The canonical metric owner must map those facts. Until that mapping exists, the protocol makes no new denominator assertion. This reconciles the old prose/YAML conflict without redefining Organizing Rule 5.

### 4.13 Detecting mechanical or unsupported abstention

Public positive controls, known-groundable seeds, exact owner-backed refusal reasons, acquisition records, recall/freshness evidence, and equal publication can detect a mechanically locked positive path or generic unsupported refusal. They do **not** prove abstention is no longer strategically dominant.

A cautious implementation may pass every public control, give precise owner-backed reasons, and refuse all three unseen real cases. It remains compliant. T6's deeper grounding-economics and incentive problem stays open; INT-R9 merely makes some refusal patterns inspectable.

### 4.14 Interface with amended INT-R1

INT-R9 consumes the delivered **`ObligationCoverageEnvelope`**, not the obsolete placeholder name.

- `known_incomplete` is NO-GO for the affected protected action.
- `open_world_unresolved` is NO-GO whenever the unresolved remainder may be material. The amended INT-R1 says this is the current baseline standing.
- A future `bounded_complete` permits continued evaluation only relative to the exact closure basis, obligation-language/compiler version, scope, purpose, audience, cutoff, maintained semantic assumptions, current independent review, challenge/expiry standing, and visible unknown-world rider. It is never world completeness and never promotion by itself.
- If a different narrower protected action is defensible, it requires a new prospective identity, envelope, preregistration, and fresh cases. The same scored claim may not be narrowed after inspection.

The old rung “if INT-R1 is weaker, narrow the criteria and public claim” is withdrawn because it contradicted the protocol's own anti-selection purpose.

---

## 5. Counterexamples And Failure Modes

| Mechanism | Rule-following adversary | Required reaction / residual |
| --- | --- | --- |
| three scopes | opens A/B/C, each ordinal zero and local `delta` | allowed locally; no family number is claimed |
| adaptive repair | learns from slot 1, publishes repair, succeeds on slot 2 | honestly labeled adaptive; no rescore and no family theorem |
| materiality | calls adverse dissent nonmaterial after seeing direction | dispute; no favorable late classification |
| purposive pool | authors all pairs around known strengths | disclose upstream tractability residual; no “unbiased selection” claim |
| friendly panel | formally eligible people share funder/network/stake | evidence and explicit conflict disposition; declaration alone insufficient |
| constant refusal | passes controls but refuses every unseen case with owner-backed reasons | compliant; anti-abstention claim remains narrow |
| post-result scope narrowing | removes material obligation by shrinking claim | NO-GO; new scope/version/fresh cases only |
| YAML conformance | implementer loads old structured literals | impossible after comments-only demotion |
| hand-coded old binding | departed author left a semantic case shortcut | automatic NO-GO; departure does not cleanse provenance |
| hidden rerun | favorable later seed replaces first output | first result-bearing run remains scored |
| leaked holdout | answer accessed before output freeze | void/dispute; keep chronology; no replacement |
| later unjustified promotion | material defect found after publication | append challenge and canonical suspension/correction/withdrawal/supersession; preserve history |

A positive-seeking insider can still exploit covert collusion or upstream pool choices outside observable custody. The claim expressly excludes those. A blame-avoiding insider can still refuse every unseen case with supported reasons. The protocol does not pretend otherwise.

---

## 6. Benchmark Or Fixture Proposal

The detailed package is in [fixture-specifications.md](int-r9/fixture-specifications.md). Four evidence layers remain:

1. visible public regression: 13 real + 2 synthetic + public mutations;
2. sealed new primary case;
3. separately sealed adjacent case under the same freeze; and
4. sealed semantic falsifiers: source flip, obligation removal, wrong scope, opaque identity.

Required amendment falsifiers include:

- three distinct local scopes each receiving ordinary local accounting must still yield **no family claim**;
- any result-informed repair is labeled adaptive and cannot rescore the earlier slot;
- an unforeseen direction-bearing materiality decision yields dispute;
- three friendly same-network humans do not qualify from declarations alone;
- material amended-INT-R1 weakness cannot be cured by narrowing the same scored claim;
- the retired YAML parses to `null` and exposes no loadable protocol fields; and
- a canonical S0-GAP-02 supersession is required before any replacement machinery is accepted.

A passing battery means only that the named revision, environment, cases, mutations, evaluator, protocol, owners, and assumptions satisfied the tested predicates. It proves neither representativeness nor family-risk control.

---

## 7. Artifact Contract Sketch

These are research shapes, not contracts. Full details are in [state-machine-and-artifact-contracts.md](int-r9/state-machine-and-artifact-contracts.md).

### 7.1 `FirstPromotionPreRegistration` semantic minimum

- immutable protocol/version/baseline/freeze references;
- committed case frame/pool/selection/order/stopping/no-substitution;
- procedural and canonical-owner predicate references;
- prospective materiality decision specification;
- case/expectation/custody/adjudicator identities and evidence/disclosures;
- amended-INT-R1 envelope reference for each exact protected action;
- result-independent publication and correction rules;
- CTM receipt/transaction/verification/admission/action times;
- explicit `numeric_family_claim = none` as explanatory prose, not a new runtime field; and
- authority boundaries denying capability, compliance, family risk, and owner appointment.

### 7.2 `FirstPromotionAttemptRecord`

Records slot order, exact freeze, input/output/expectation reveal receipts, local canonical owner receipts, prior terminal refs, adaptive-repair ancestry, public regression, falsifiers, adjacent result, deviations, incidents, and chronology. It never aggregates local risk.

### 7.3 `FirstPromotionAdjudicationRecord`

Records identified humans, corroborating independence evidence, declared residuals, conflicts/recusals, raw signed votes, abstentions, criterion findings, prospective materiality refs, unresolved dissent, bounded disposition, and public-claim permission. Populated fields are not proof; evidence and verifier paths decide admissibility.

### 7.4 State and one-lattice rule

`drafted`, `sealed`, `candidate_inspected`, and `adjudicated` are custody-workflow facts. `promoted` requires the existing canonical promotion owner plus INT-R9 procedural admissibility. `refused`, `void`, and `disputed` retain canonical owner reasons. Correction uses existing currentness/claim owners. No workflow label becomes a parallel authority status.

### 7.5 Time partial order

```text
protocol_and_pool_transaction_visible
  < selection_execution_transaction
  < implementation_freeze_complete
  < primary_input_reveal
  <= first_inspection
  <= candidate_output_freeze
  < expectation_reveal
  <= adjudication_action
```

If clock accuracy cannot prove strict order, prospectivity is not established. Later verification cannot backdate transaction visibility.

---

## 8. Later Integration Handoff

| Producer/fact | Persisted evidence | Bridge / consumer | Verification | Current standing |
| --- | --- | --- | --- | --- |
| protocol and selection group | selection specification, commitments, receipt | S0-GAP-02 to governance/run control | commitment, randomness, conflicts, CTM order | missing |
| case authors/custodian | primary/adjacent/input/expectation packages | S0-GAP-02 to frozen run/evaluator | hiding/binding, access, reveal, versions | missing |
| canonical GY owners | N9/refusal/firewall/local confidence receipts | existing chain to adjudication/closeout | live replay; no family aggregation | local primitives exist; positive capability absent |
| amended INT-R1 producer | `ObligationCoverageEnvelope` | N9/N11 protected-action use | exact scope, basis, assumptions, review/currentness | current `open_world_unresolved`; positive blocked |
| materiality owners | prospective materiality records | panel/closeout | competence, conflicts, rule/time | unresolved; sealing blocked |
| named panel | signed votes/evidence/residuals | S0-GAP-02 challenge to closeout | identity, relationships, access, quorum | absent |
| closeout/currentness owners | public terminal and corrections | Atlas/public/expert/machine | completeness, bounded wording, lineage | consumer waiting |

No row appoints a package or owner. A future family-risk capability belongs to a separately accepted canonical confidence-ledger extension, not this handoff.

---

## 9. Promotion And Kill Rules

### 9.1 Promotion rule

For slot `s_i`, procedural promotion is admissible only if it is the earliest unresolved committed slot; prospectivity/order/freeze/public-regression rules hold; every applicable canonical owner permits the exact bounded claim; amended INT-R1 permits the protected action; primary and adjacent behavior are evaluator-correct; no heldout-case mechanism is found; source-flip and obligation-removal relations pass; prospective materiality is established; named evidence-backed panel admits; no material dissent/NO-GO applies; every prior terminal is published; and public wording stays within the declared boundary.

There is no conjunct for family `delta`, cumulative spend, or sequence ordinal because no such canonical property exists for this protocol.

### 9.2 Predeclared NO-GO reasons

NO-GO includes late preregistration; wrong/replaced slot; any current corpus case as decisive holdout; ua-msme as primary/adjacent; role-only adjudicators; missing evidence/quorum; answer leakage; post-reveal asset change; heldout-case binding; hidden rerun; result-based substitution; post-result criterion/threshold/materiality/exclusion/stopping change; public regression failure; unchanged positive after source/obligation removal; wrong adjacent freeze/behavior; canonical owner fail/unknown/stale/bypass; amended-INT-R1 `known_incomplete` or material `open_world_unresolved`; post-result narrowing of the same action; result-independent publication breach; useful-rate influence; exclusion without prospective owner-backed isolation; or overbroad public wording.

### 9.3 After failure and amendment

A failed/refused/void slot remains the attempt and is published before the next reveal. Repair creates a new frozen revision and is adaptive continuation. Criteria, selected cases, order, materiality rules, stopping, and publication cannot change. No family number follows.

Before any inspection, a mis-specified preregistration may be retired only with affirmative no-access proof, public diff, and new commitments. After inspection, no amendment rescoring is allowed. After promotion, changes are append-only correction/suspension/withdrawal/supersession/challenge actions.

### 9.4 Protocol kill rules

Kill/redesign if selection cannot be reproduced; custody cannot hide/separate answers; named humans/evidence are unavailable; materiality is unresolved; the public battery or sealed cases were tuned against; no-bespoke review becomes a literal-ID scan; adjacent cases are paraphrases/different freezes; a parallel status/risk/oracle owner appears; three local scopes are described as one budget; post-result narrowing can rescue coverage; anti-abstention controls are described as proof; a research sketch becomes executable; failed runs can disappear; success is required/rewarded; or public wording exceeds S0-K16.

### 9.5 Audit §8 kill-rule walk

| Audit kill rule | Amendment closure |
| --- | --- |
| three distinct scopes each start with fresh `delta` | trace is explicitly admitted; no sequence-level numeric claim is made |
| “cumulative” is an author-written field | cumulative scope/spend/ordinal fields and claims are absent; local receipts stay separate |
| failed-slot risk disappears in next scope | INT-R9 makes no family-risk disposition; chronology and local histories remain |
| post-result scope narrowing rescues coverage | expressly NO-GO; new action means new prospective identity/version/cases |
| materiality decided after direction | automatic dispute unless direction-blind rule/evidence was sealed |
| YAML remains executable | comments-only; no mappings, identifiers, enums, transitions, or conformance path; parse result `null` |

### 9.6 No-promotion survivability

Before sealing, governance signs that completion is assessed on adherence, evidence quality, acquisition work, challenge response, and honest repair—not outcome sign. Promotion-contingent bonuses, milestone credit, reviewer pay, or manager evaluation are forbidden. Every terminal uses the same durable public artifact class, release channel, review agenda, and archival priority. Queue exhaustion fulfills the mandate.

This cannot eliminate informal prestige differences. It makes formal retaliation or suppression visible and nonconforming.

---

## 10. Open Questions For Consolidation

1. **INT-R1 producer/bridge:** who may issue/admit a future envelope without self-scoring, and how is a new narrower action given a fresh prospective identity?
2. **INT-R10 / GY-GAP2:** a future numeric family claim needs pre-execution local caps, live recomputed family projection, canonical owner extension, and re-audit. Theorem B remains audit-pending.
3. **S0-GAP-02:** only a governed canonical supersession may replace it; no sibling equivalent.
4. **Materiality:** which existing competent owners decide source, obligation, deviation, dissent, and challenge materiality before direction is known?
5. **INT-R5:** how are competence, delegation, named-person eligibility, and relationship conflicts evidenced?
6. **INT-R8:** how do public surfaces retain purposive-pool limits, independence residuals, negative outcomes, INT-R1 remainder, and absence of a family number?
7. **Useful-design metric:** which canonical owner maps selected, uninspected, retired, inspected, void, refused, disputed, promoted, and unreached facts? INT-R9 does not define it.
8. **Pool construction:** what external frame and author-selection process can reduce tractability bias, or how prominently must purposive construction remain visible?
9. **Human independence:** what minimum evidence and disposition apply to same-funder, shared-governance, contractor, network, and reputational ties?
10. **Duplicate abstractions:** reject a second promotion status, confidence ledger/family scope, oracle service, time vocabulary, public lattice, challenge owner, or universal envelope.

No evidence requires reopening S0-K13, S0-K15, or S0-K16.

### Consolidation kernel

Consolidation may accept only the following: current corpus is regression, never holdout; ua-msme is excluded from primary and adjacent roles; firstness is prospective finite order; selection is non-discretionary after pool commitment; pool-level tractability remains disclosed; packages are independently sealed; named evidence-backed humans and prospective materiality are mandatory; result-informed repair is adaptive; **no sequence-level numeric risk claim is made**; local scopes remain separate; current amended-INT-R1 standing blocks a positive; falsifiers are semantic and bounded; every terminal is public; no positive is assumed; metric chronology does not redefine the denominator; S0-GAP-02 retains custody ownership; and passage supports only the named procedural claim.

---

## Final Answer To The Research Question

PolicyOS cannot prove an absolute absence of cherry-picking around an `n = 1` historical event. It can preserve a checkable prospective record showing that observable case, order, run, criterion, materiality, reviewer, exclusion, and firstness choices were governed before their result-bearing direction was known; that public cases were not miscalled holdouts; that ua-msme did not re-enter as decisive or adjacent evidence; that named human adjudication and dissent were preserved; and that every negative outcome remained public.

Because implementation repair is permitted after earlier outcomes, the protocol is adaptive. At the pinned source, three problem scopes do not share one budget and no canonical adaptive family theorem exists. The amended protocol therefore makes **no sequence-level numeric false-promotion claim**. A first positive remains possible but unpromised. With current INT-R1, S0-GAP-02, case-custody, materiality, and staffing standing, no positive attempt is eligible. Refusal, dispute, void, no attempt, and `exhausted_without_promotion` remain fully valid outcomes.
