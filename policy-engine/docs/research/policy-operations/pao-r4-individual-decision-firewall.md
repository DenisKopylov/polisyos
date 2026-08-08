---
title: PAO-R4 — Policy-to-Individual-Decision Firewall
research_id: PAO-R4
status: amended_research
research_only: true
repository: DenisKopylov/polisyos
audited_commit: a27c3da9942b03881dbee1005a8a1e44e5ac44b4
audit_commit: 69182c079fb5dc99808d7cd27874d50433efd5a4
pinned_repository_commit: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
source_equivalent_original_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
result_standing: GO_WITH_REVISIONS
adoption_status: NO_GO_pending_independent_conformance
authoritative_for:
  - amended research definition of the empirical-population-to-individual semantic boundary
  - research-only handoff and detection semantics for policy exports
  - research-only authority-scoped refusal frontier
  - bounded returning-evidence claims inside a declared governed integration boundary
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner or vendor appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional compliance conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog or system-design decision
---

# PAO-R4 — The policy-to-individual-decision firewall

## 1. Amended result

**A PolicyOS artifact may cross toward a governed case-system boundary only when its semantic class
is established, its source basis and denied uses remain attached, its use is bounded to a permitted
purpose, and every protected-action consultation inside that boundary is subject to a mandatory
consumer gate and complete returning evidence. An empirical or pointwise-recoverable artifact whose
individual use cannot be made observable is refused. A competent normative general rule is not
refused merely because it is executable: it may travel only as rule-level input under an external
authority's own fact-finding and procedure, without becoming PolicyOS case authority.**

**Research standing remains `GO_WITH_REVISIONS`; adoption remains `NO_GO` pending independent
conformance verification of this amendment.** The amendment does not claim implementation. The
pinned repository still lacks the individual-use vocabulary, policy-to-case gate, governed external
consumer, complete returning-evidence chain, and composition transcript required for a capability
claim.

The positive firewall proposition is deliberately bounded:

> Within a named governed integration boundary, and only for the events and channels whose complete
> denominators are independently reconciled, the contract can establish that every observed
> protected-action consultation was either permitted or blocked. It cannot establish institution-wide
> non-use, human memory, off-ledger copies, or activity outside that boundary.

## 2. Scope and binding architecture

The identity ruling assigns PolicyOS ownership of the **individual-decision firewall**, while the
individual determination remains external:
`policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:123-139@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, finding **Individual-decision firewall**. The
anti-roles remain binding: PolicyOS is not an administrator, executor, case-management system,
court, notification channel, payment system, or CRM
(`policyos-identity-and-custody-boundary.md:88-91@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`).

The firewall therefore owns the boundary claim and evidence semantics:

1. which semantic classes may cross toward a named consumer;
2. which uses remain denied and how those denials survive derivation, projection, and correction;
3. what consumer-side observable makes individual use visible;
4. what implementation evidence returns and which bounded claim it can support; and
5. when the only honest result is refusal or `NOT_ESTABLISHED`.

It does not own case fact finding, legal applicability, competent authority, the administrative act,
individual reasons, review, notification, payment, sanction, remedy, or the case workflow.

The following ratified findings constrain the amendment:

- **`S0-K05`** — observation, transport, or projection cannot create authority;
- **`S0-K07`** — projection cannot mint authority;
- **`S0-K11`** — protected actions require equivalent, action-specific protection;
- **`PV-K04`** — projection may reduce detail but may not amplify authority or permission, and denied
  uses do not shrink;
- **`INT-K02`** — a `delta` is inseparable from its declared obligation set and assumptions; PAO-R4
  transfers the bounded lesson that an empirical claim stripped of its basis changes meaning.

The amendment also applies two repository disciplines registered at the documentation pin:

- **`P35`** — every set-level statement names both its path denominator and file-type denominator;
- **`P36`** — adjacency to an owner is not authority to appoint that owner;
- **`P37`** — every predicate a gate turns on has a frozen provenance class, and a predicate that is
  merely asserted, institutionally supplied, or not established cannot yield an authority-grade
  positive.

See
`policy-engine/docs/reference/policy-design-case-failure-patterns.md:77-80@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`.

## 3. Formal population/individual boundary

### 3.1 Four semantic classes

The firewall does not classify an artifact from its filename, field names, or “aggregate” label. It
first places the artifact in one of four semantic classes.

#### E — empirical population summary, probability, or effect

Let:

- \(\Omega\) be the universe of possible subjects under a declared subject identity, time,
  jurisdiction, and tenant scope;
- \(B\) be the empirical claim basis: population predicate, geography/jurisdiction, time, source and
  selection process, method, maintained assumptions, intended use, audience, and cutoff;
- \(C_B(x)\in\{0,1\}\) assign subject \(x\) to the declared reference class;
- \(R_B=\{x\in\Omega:C_B(x)=1\}\);
- \(D_B\) be the data-generating or causal object identified under \(B\);
- \(\Phi\) be a population functional over \(D_B\), such as a mean, rate, distribution, treatment
  effect, calibrated group risk, or elasticity;
- \(\theta=\Phi(D_B)\) be the bounded empirical result; and
- \(L\) be its limitations and denied-use set.

An empirical population claim is

\[
P_E=(R_B,B,D_B,\Phi,\theta,L).
\]

Its quantifier and estimand are population-level. It is not a normative rule and does not itself say
what a competent body must do to a particular person.

#### G — normative general rule under an external competent authority

A normative rule is a distinct object:

\[
G=(A_G,J_G,T_G,Q_G,\Gamma_G,L_G),
\]

where \(A_G\) is the externally supplied authority claim, \(J_G\) and \(T_G\) are jurisdiction and
time, \(Q_G\) is the rule predicate applied to case facts, \(\Gamma_G\) is the normative consequence,
and \(L_G\) contains limitations and denied uses. PAO-R4 does not determine whether \(A_G\) is legally
competent or whether \(Q_G\) is satisfied in a case. Those are external institutional premises and
case-system functions.

A normative rule can be intentionally applicable to a person:

\[
G\land Q_G(F_x)\models \Gamma_G(x).
\]

That entailment is not ecological inference. It is how a competent general rule is supposed to
operate after external fact finding and procedure. Transporting \(G\) does not make PolicyOS the
case authority and does not establish that the rule is applicable, valid, or legally sufficient.

#### X — individual or pointwise-recoverable artifact

An artifact is in class X when, under the permitted history and auxiliary-information model, it
resolves a subject or supplies a pointwise mapping capable of determining or materially constraining
a protected action. Person rows, individual scores, singleton aggregates, deterministic partition
tables, differencing query families, rankings, watchlists, and final case recommendations are
examples. The test is semantic and compositional, not syntactic.

#### S — synthetic non-case example

A class-S artifact is explicitly synthetic and remains non-resolvable to any real subject under the
named history and auxiliary-information model. A “synthetic” label does not control. If the example
maps to a real subject, it is reclassified as X.

Unknown or mixed class is not silently assigned to E or G. It returns `NOT_ESTABLISHED`; for a
protected case-system handoff the export is refused.

### 3.2 Empirical non-entailment

For a class-E artifact that is not pointwise recoverable under the admitted history, the core rule is:

\[
P_E\land C_B(x)=1\not\models F_x,
\]

and therefore

\[
P_E\land C_B(x)=1\not\models I_x,
\]

where \(F_x\) are the person's case facts and
\(I_x=\psi(x,F_x,G,A,P)\) is an individual determination made under a competent general rule \(G\),
authority \(A\), and procedure \(P\).

Membership makes arithmetic substitution possible; it does not establish the person's outcome,
eligibility, sanctionability, risk state, priority, credibility, reason, or entitlement. A calibrated
probability remains a probabilistic statement. An ecological relation remains an aggregate relation.
A separately justified individual inference would need, at minimum, an individual target, justified
reference-class and transport relation, current case facts, treatment of missing/contradictory facts,
a competent normative rule and procedure, and authority for the protected action. PAO-R4 supplies
none of those merely by exporting \(P_E\).

This non-entailment does **not** govern class G. The original formalism did not admit normative rules
into \(P_E\); the audited defect arose because the handoff contract nevertheless grouped a general
rule with empirical estimates and refused it for being executable. Sections 3 and 4 now use the same
semantic classes.

### 3.3 Pointwise recoverability

For artifact \(a\) and a named permitted history/auxiliary-information model \(H\), define:

\[
\operatorname{individualizable}(a,H)=1
\]

iff there exists a resolvable subject \(x\) such that \(a\) together with \(H\) reveals an individual
fact or supplies a pointwise mapping that determines or materially constrains a protected action for
\(x\).

The predicate is applied as follows:

- if \(a\) is class E and `individualizable(a,H)=1`, it is reclassified as X and refused for a
  governed case-system crossing;
- if \(a\) is class S and becomes resolvable, it is reclassified as X;
- if \(a\) is class G, individual applicability is expected and is **not** by itself a refusal
  reason. The rule may travel only as rule-level input with no PolicyOS authority effect, under the
  external authority's own fact finding and procedure;
- if the semantic class or \(H\)'s completeness is not established, the authority-grade result is
  `NOT_ESTABLISHED` and the protected crossing is refused.

This classification closes the three audit artifacts:

| Audit artifact | Semantic result | Crossing result |
|---|---|---|
| A — singleton empirical rate | E becomes X because the cell resolves one person and reveals the person's outcome | `REFUSE_EXPORT` |
| B — complete deterministic empirical partition | E becomes X because the family is a pointwise decision surface | `REFUSE_EXPORT` |
| C — normative universal rule | G; executability is expected, not evidence of PolicyOS case authority | `ALLOW_RULE_LEVEL_INPUT` with `authority_effect: none` and external applicability `NOT_ESTABLISHED` |

### 3.4 Observable individual use

Inside the declared governed integration boundary, the firewall uses a conservative observable rule:

> A PolicyOS artifact or its derivative is **used** in a protected individual action whenever the
> instrumented case process consults, displays, queries, invokes, supplies, thresholds, ranks,
> recommends from, evidentially weights, explains with, or routes by that artifact while a subject and
> protected action are resolved.

Consultation is enough. The consumer is not asked to decide whether the action “would have changed.”
This intentionally produces false positives at the boundary rather than silent false negatives. A
counterfactual effect estimate may be recorded as a narrower analytical claim only when independently
validated; an operator's answer is `consumer_asserted` and cannot make a gate green.

A firewall violation occurs when such use is for a purpose in the artifact's `may_not_use_for` set,
when a class-E/X artifact fills an individual fact or authority slot, when a class-G rule is represented
as PolicyOS's individual determination, or when mandatory evidence is absent. It is silent when no
export-context gate, consumer-use gate, evidence reconciliation, or `NOT_ESTABLISHED` result becomes
visible.

Residual false-negative boundary: prior human memory, off-ledger reading, screenshots, unlinked
narratives, hidden local models, and other channels outside the declared instrumentation may still
influence a case without an event. Those channels are outside the positive firewall claim and may
force refusal of an otherwise readable/actionable class.

### 3.5 `P37` predicate-provenance table

Every load-bearing predicate is assigned exactly one provenance class and the class is frozen when
the artifact/request is admitted. `consumer_asserted`, `institutionally_supplied`, and
`not_established` cannot yield an authority-grade positive. They either fail closed for the protected
action or downgrade the claim to transport-only/observation-only.

| Gate predicate | Required input | Provenance class when positive is permitted | If only asserted/supplied/unknown |
|---|---|---|---|
| Artifact bytes, digest, class-declared fields | canonical artifact and parser | `recomputed` | malformed/unresolved → `NOT_ESTABLISHED` |
| Source and derivation denied-use union | complete controlled lineage | `recomputed` | incomplete lineage → `NOT_ESTABLISHED` |
| Presence of every registered basis field | registered basis obligations + artifact | `recomputed` | missing field → `BLOCK_BASIS` |
| Truth and semantic completeness of `B` and `L` | independent source/obligation evidence | `independently_reconciled` | declaration alone is `institutionally_supplied` or `consumer_asserted`; no authority-grade positive |
| E/G/X/S semantic class | content plus source-authority evidence | `recomputed` for empirical/synthetic form and `independently_reconciled` for source identity | external competence remains `institutionally_supplied`; transport may be candidate-only, applicability is `NOT_ESTABLISHED` |
| Completeness of history and auxiliary model `H` | named release/query transcript + independent inventory | `independently_reconciled` | incomplete or deliberately narrow model → `NOT_ESTABLISHED` |
| `individualizable(a,H)` | artifact, behavioral interpreter, complete `H` | `recomputed` | no complete `H` → `NOT_ESTABLISHED`/refuse protected crossing |
| Declared request purpose | request record | `consumer_asserted` | can block an openly denied request but can never prove later permitted use |
| Protected-action semantic class | action event + canonical effect mapping | `recomputed` or `independently_reconciled` | benign label alone → `NOT_ESTABLISHED` |
| Consultation/invocation in a protected action | instrumented data-flow/use event | `recomputed` | absent instrumentation → outside boundary / no complete claim |
| Complete protected-action denominator | independent case-event totals | `independently_reconciled` | consumer total alone → no complete non-use claim |
| “Would the action have changed?” | validated removal experiment or independent causal evidence | `independently_reconciled` | operator answer is `consumer_asserted`; cannot make gate green |
| External rule authority/applicability | competent institution and external procedure | `institutionally_supplied` | may support rule-level transport only; never a PolicyOS authority or compliance positive |

#### Falsify-the-declaration probes

- **False `B` declaration:** keep “complete basis” in the artifact while omitting a material
  assumption. Field presence remains green, but semantic completeness is not independently
  reconciled; the result is `NOT_ESTABLISHED`, not `ALLOW_NON_INDIVIDUAL`.
- **Scenario S-1:** all declared in-boundary events reconcile while an operator later relies on a
  remembered aggregate outside instrumentation. The bounded in-boundary receipt may remain true, but
  institution-wide non-use is unavailable and the scenario is explicitly outside the positive claim.
- **Scenario S-2:** the operator asserts that the artifact was immaterial while instrumented display
  occurred. The conservative consultation rule still triggers the denied-use gate; the false
  counterfactual declaration cannot keep it green.

## 4. Handoff contract

### 4.1 Authority-band rule

The Stage-0 authority-band lens is controlling:
`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:46-88@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, with the binding application note at `:164-176`.
A strict prohibition is valid when it binds what may be claimed or treated as determinative in the
authority band. It must not prohibit candidate-band computation or transport merely because the
artifact is executable.

A firewall predicate over **executability** would forbid PolicyOS from exporting its own governed
core output: the obligation/admissibility calculus is itself an executable general rule applied to a
case. Executability is therefore a candidate-band property. The firewall binds **authority to
determine** and prohibited empirical use. It asks what semantic class the artifact belongs to, whose
authority it represents, what case slot it fills, and whether the use is observable—not whether a
machine can execute it.

### 4.2 Crossing classes and forms

The default authority-grade result is refusal. Candidate-band transport can be narrower than an
authority positive.

| Semantic class | Permitted crossing form | Conditions | Required denied-use effect |
|---|---|---|---|
| E — empirical aggregate/estimate/effect | Population/cohort aggregate, interval, distribution, or policy estimate | `individualizable(a,H)=0` under independently reconciled `H`; visible basis; no subject/case payload; purpose is non-individual | deny every individual-use purpose in §5 |
| G — normative general rule | Rule-level input, including executable parameters needed to express the rule | source identity reconciled; external authority/applicability remains external; case facts, reasons, procedure and final act are not supplied by PolicyOS; `authority_effect: none` | deny representation as PolicyOS individual determination, reason, evidence finding, or authority grant |
| X — individual/pointwise-recoverable | no governed crossing toward a case system for a protected action | internal candidate research is not forbidden; a separate competent architecture act would be needed for any other bounded use | refuse protected crossing |
| S — synthetic non-case example | non-resolvable synthetic example for training/communication | `individualizable(a,H)=0`; synthetic provenance; no mapping to real case | deny all real-case use and representation as evidence about a person |
| unknown/mixed | none for protected case-system handoff | semantic class or decisive predicate not established | `NOT_ESTABLISHED` and refuse |

“Anonymized” remains an empirical proposition about resolution resistance under named auxiliary
information and release history. It is not an independent permission class.

### 4.3 Complete crossing predicates

A crossing can receive a bounded positive only when every decisive predicate below is recomputed or
independently reconciled:

1. the semantic class is established;
2. the artifact and lineage resolve and the basis obligations are present;
3. source/derivation denied uses are unioned monotonically under `PV-K04`;
4. the named `H` inventory is complete enough for the claimed non-resolution scope;
5. an E or S artifact is not individualizable under `H`;
6. the named consumer and declared purpose are recorded, without treating that declaration as proof
   of later use;
7. every protected-action consultation in the governed boundary routes through the consumer gate;
8. imports, derivatives, consultations, blocked attempts, and protected actions reconcile to an
   independent denominator; and
9. the exact claim wording stays within the claim-boundary table in §11.

A merely declared premise cannot satisfy any authority-grade predicate. Candidate transport of G may
proceed with an explicit external-authority premise, but the applicability/competence claim remains
`NOT_ESTABLISHED` to PolicyOS.

### 4.4 Authority-scoped refusal frontier

Refuse a protected case-system crossing when:

- an E or S artifact is subject-resolvable or pointwise-recoverable under the named `H`;
- an empirical score, label, rank, propensity, watchlist, recommendation, deterministic partition,
  or query family is capable of filling a protected individual slot;
- a person/case row, stable pseudonym, subject resolver, or case-binding key crosses;
- a small-cell or multi-export family is composition-unsafe or its history is incomplete;
- an unknown/mixed artifact cannot be distinguished from empirical individualization;
- a G artifact is presented as PolicyOS's final determination, individual reason, case fact, or
  authority rather than external rule-level input;
- denied uses shrink through projection, derivation, correction, or relay;
- the actual use can be known only through voluntary, selectively sampled, self-attested, or
  unverifiable reporting; or
- a material off-ledger route remains and the artifact is individually actionable through it.

A competent normative rule is **not** refused merely because it is executable. Artifact C therefore
passes the executability test as G, while an empirical decision tree with identical syntax is X and
is refused because its semantic class and authority effect differ.

## 5. Prohibited individual-use matrix

Every permitted E/S crossing carries, at minimum, the following `may_not_use_for` purposes. A G
crossing also denies any representation that PolicyOS itself supplied the case facts, authority,
reason, or final determination.

| Denied purpose | Protected effect | Why an E artifact is insufficient |
|---|---|---|
| `individual_eligibility_determination` | access to benefit, licence, status, or programme | reference-class membership does not establish case-rule facts |
| `individual_benefit_or_burden_amount` | amount paid, charged, withheld, recovered, or allocated | population response/average does not determine the lawful amount |
| `individual_sanction_or_enforcement` | penalty, inspection, enforcement, exclusion, or adverse action | statistical generalization cannot replace case proof and competent procedure |
| `individual_risk_scoring_or_profiling` | risk label, score, propensity, or profile | a base rate is reference-class conditional, not an individual state |
| `individual_priority_or_triage` | queue order, urgency, or scarce-resource priority | group effects do not establish the person's relative rank |
| `individual_investigation_or_surveillance_targeting` | selection for scrutiny, audit, investigation, or monitoring | population association is not individualized suspicion or necessity |
| `individual_credibility_fraud_or_integrity_assessment` | credibility, fraud, honesty, or integrity inference | group statistics do not prove conduct or credibility |
| `individual_service_access_or_routing` | channel, service level, referral, or denial of human access | aggregate efficiency does not decide a person's route |
| `individual_evidence_weighting_or_adverse_inference` | weight assigned to case evidence or inference from absence | population evidence cannot silently alter the adjudicative record |
| `individual_reason_generation` | stated grounds for an individual act | a population explanation is not the actual case-specific ground |
| `individual_human_review_selection_or_intensity` | whether and how much human review occurs | review cannot be rationed by the same ungrounded inference |
| `individual_recommendation_materially_affecting_rights` | recommendation relied on for a protected action | formal finality is irrelevant when the empirical artifact enters the protected action |
| `case_closeout_or_final_determination` | closing, approving, denying, or otherwise determining the case | transport cannot mint case authority |
| `policyos_as_case_rule_authority` | representation that PolicyOS owns or validated external normative authority | the identity ruling assigns the firewall, not the sovereign/administrative function |

A human click does not cure a denied use. Under the amended conservative rule, instrumented
consultation during a protected action is sufficient to trigger the gate.

## 6. Detection semantics — four observation locations

### 6.1 Artifact-local observable

These predicates are recomputed from the artifact and controlled lineage itself:

| Predicate | Input | Verdict when false/incomplete |
|---|---|---|
| person/case row or explicit subject key present | artifact bytes and canonical parser | `REFUSE_EXPORT` |
| individual score/rank/watchlist/final recommendation present | artifact semantics | `REFUSE_EXPORT` |
| registered basis field absent | basis obligation set + artifact | `BLOCK_BASIS` |
| denied-use set shrank from a resolved source | source/derivation lineage | `BLOCK_PERMISSION_AMPLIFICATION` |
| artifact/lineage/digest cannot resolve | artifact reference and registry | `NOT_ESTABLISHED` |

Artifact-local inspection cannot prove that an omitted material assumption does not exist.

### 6.2 Export-context observable with named `H`

These predicates require more than the bytes: a named release/query history, auxiliary-information
model, semantic interpreter, and independent inventory.

| Predicate | Required context | Incomplete-input verdict |
|---|---|---|
| subject resolution through joins or singleton cells | `H`, population inventory, linkage model | `NOT_ESTABLISHED`; refuse protected crossing |
| deterministic/pointwise recoverability | artifact family, behavioral interpreter, case-feature domain | `NOT_ESTABLISHED`; refuse protected crossing |
| composition safety across exports/queries | complete controlled transcript and release-family identity | `BLOCK_COMPOSITION` when unsafe; otherwise unknown → `NOT_ESTABLISHED` |
| E/G/X/S class | content, source identity, authority provenance | unknown/mixed → `NOT_ESTABLISHED` |
| source basis semantic completeness | independent obligation/source reconciliation | declaration only → no positive |

These are export-context checks, not claims that the artifact alone reveals every risk.

### 6.3 Downstream use-context observable

Inside the governed integration boundary, the consumer gate receives the resolved subject, protected
action class, exact artifact/derivative digest, and instrumented consultation event. A consultation
for a denied purpose produces `BLOCK_PURPOSE` before the action. A bypass produces one
`FIREWALL_VIOLATION` record. Purpose synonyms are mapped from action effects, not trusted strings.

The returning evidence reconciles:

- issued artifacts;
- imports and derivatives;
- consultations/invocations;
- gate verdicts and bypasses;
- protected-action totals; and
- the exact governed boundary and interval.

No in-boundary positive is available when the protected-action denominator or instrumentation is not
independently reconciled.

### 6.4 Outside the declared boundary — not observable

The following remain outside a complete positive claim unless separately brought into a governed,
reconciled boundary:

- an operator later relies on memory of a planning artifact;
- screenshots, transcription, copied numbers, or uncontrolled derivatives;
- hidden local models or prompts trained from an export;
- reference-class shopping performed outside the transcript;
- semantic purpose relabeling outside the action-effect mapping;
- a relay that strips lineage before the governed consumer;
- external joins outside the named auxiliary model; and
- selective, false, or omitted reports beyond independent reconciliation.

For an individually actionable class with a material path through these channels, refusal remains the
only enforceable firewall result. Complete in-boundary evidence never establishes institution-wide
non-use. Scenario S-1 belongs here.

## 7. Returning-evidence interface — semantics, not schema

### 7.1 Issue evidence

For every crossing, PolicyOS retains the exact artifact/derivation digest, semantic class, source
basis and basis-obligation identity, complete denied-use union, named consumer and permitted request
purpose, governed-boundary identity, `H` identity, issue time, and release-history position.

### 7.2 Use evidence

For every import, derivative, consultation, gate attempt, and protected action in the governed
boundary, the consumer returns:

- artifact and derivative digests plus lineage;
- a scoped subject reference sufficient for reconciliation but not public identity;
- protected-action effect class, not only a purpose string;
- the instrumented consultation/invocation event and stage;
- consumer verdict and reason;
- human role and override record;
- outcome/reason reference, consumer version, and event time; and
- the predicate-provenance classes frozen at admission.

This is semantic content only. It does not ratify a wire format, API, database, or case-system model.

### 7.3 Trust and completeness

A complete in-boundary claim requires:

- content-bound committed issue/use records;
- append-only history;
- a complete derivative lineage within the boundary;
- independently reconciled protected-action and consultation denominators;
- non-producer verification where a verification claim is made; and
- fail-closed treatment of missing, late, contradictory, selectively sampled, unresolved, or
  self-attested-only evidence.

Such failure yields `FIREWALL_CLAIM_NOT_ESTABLISHED`; it never means “no prohibited use.” Content
binding proves what was recorded, not the truth of a counterfactual assertion. Scenario S-2 is closed
by making consultation—not self-reported causal impact—the gate predicate.

### 7.4 Voluntary reporting and bounded claim lattice

The core impossibility remains unchanged:

```text
world A: no prohibited use; no report
world B: prohibited use; no report
observation: identical
```

Therefore voluntary reporting cannot establish a **complete non-use firewall claim**. A class that
requires use-time detection is refused until reporting and reconciliation are mandatory and
trustworthy.

Voluntary or sampled evidence may support only accurately bounded claims:

| Evidence posture | Maximum supported claim |
|---|---|
| no reports under a voluntary channel | no non-use inference; documented restriction only |
| one or more content-bound voluntary reports | observed incidents occurred; no completeness claim |
| known reporting denominator but incomplete participation | lower bound on observed prohibited uses |
| predeclared sampled audit with valid sampling frame | sampled-rate or interval claim for that frame, not complete non-use |
| mandatory complete independently reconciled boundary | bounded in-boundary complete-use/non-use claim, subject to residual channels |

This is a set of claim bounds under `INT-K08`, not a new status or outcome vocabulary.

## 8. Comparative selection

The selected research architecture remains a composition:

- semantic-class allow-list;
- artifact-local checks;
- named-history/auxiliary export-context checks;
- provenance-carried monotone denied uses under `PV-K04`;
- request-time purpose recording without treating it as later-use proof;
- conservative consumer-side consultation gate;
- mandatory returning evidence and independent denominator reconciliation; and
- refusal when an empirical/pointwise artifact's prohibited use cannot be observed.

Human review remains an external safeguard, not a firewall verdict. Export-permissive audit remains
insufficient. Executability alone is no longer a rejection criterion; authority effect and semantic
class are.

## 9. Legal and administrative-law transfer

The cited regimes supply comparative boundary principles, not PolicyOS compliance conclusions.
The amended line is **not narrower on the material-reliance/formal-finality trigger** than the cited
sole-automation or formal-decision comparators: upstream material use and human-mediated consultation
remain inside the engineering gate. That statement does not compare or replace the regimes' full
rights, duties, exceptions, remedies, institutional competence, hearing, explanation, or review
requirements.

The external-source ledger pins mutable sources, identifies currentness, labels inference, and keeps
every non-transfer limit.

## 10. Repository standing, source census, and owner placement

The complete census supplied by the architecture principal is recorded in the orientation ledger.
Its central result is settled at the pin:

- exact `may_not_use_for`: 106 Python files, 794 matching lines, 903 occurrences;
- disjoint token-file partition: 67 runtime, 12 scientist, 27 remainder;
- `aggregate_only`: seven all-source files;
- case-insensitive `anonymi`: seven all-source files and six Python files; and
- exact `individual_decision`, `export_gate`, and `prohibited_use`: zero files, zero matching lines,
  zero occurrences below `policy-engine/src`.

The source therefore has a pervasive denied-use carrier but no named PAO-R4 concept or gate. The
capability remains **`absent/unallocated`**.

`polisyos.core.contracts` authority envelopes and existing consumer guards are established denied-use
owners. `projection_semantics.py` is the established projection/denial-monotonicity owner.
`public_export.py` is a real public-bundle producer, but no pinned finding establishes it as the
canonical owner of every non-public, purpose-bound case-system handoff. The policy-to-case emission
chokepoint is an **open consolidation decision**. Alternatives must be evaluated by existing
responsibility and a competent owner decision; this research appoints none.

## 11. Claim-boundary table

| Claim subject | Governed boundary | Observable | Completeness premise | Residual channel | Exact allowed wording |
|---|---|---|---|---|---|
| E non-entailment | empirical semantics | class, estimand, basis and absence of pointwise recovery under named `H` | class and `H` predicates recomputed/reconciled | unmodelled auxiliary information | “This empirical population claim does not by itself establish the person's facts or determination.” |
| G transport | issue/export boundary | rule source identity, content, restrictions | source identity reconciled; authority/applicability external | invalid/inapplicable external rule | “Transported as rule-level input with no PolicyOS authority effect; applicability not established by PolicyOS.” |
| X refusal | artifact/export-context boundary | subject resolution or pointwise mapping | named `H` complete enough for the refusal witness | other unresolved routes | “Protected case-system crossing refused because the artifact is individualizable.” |
| S transport | issue/export boundary | synthetic provenance and non-resolution under `H` | `H` independently reconciled | unknown external linkage | “Synthetic non-case example within the named model; no real-case use permitted.” |
| denied-use preservation | source-to-projection/derivative chain | resolved lineage and set union | complete controlled lineage | stripped uncontrolled copy | “All known source/derivation denials are preserved in this governed chain.” |
| in-boundary consultation control | named consumer boundary and interval | consultation events, gate verdicts, protected-action denominator | mandatory instrumentation and independent reconciliation | memory/off-ledger/relay outside boundary | “Every recorded protected-action consultation in boundary B during interval T was gated and reconciled.” |
| complete non-use | only a mandatory reconciled boundary | complete imports, derivatives, consultations and protected actions | independent complete denominators | outside-boundary cognition/copies | “No prohibited consultation was observed within the declared complete boundary”; never “no use anywhere.” |
| voluntary reports | reporting participants only | received content-bound reports | no completeness premise | non-reporting uses | “N prohibited uses were reported”; no non-use inference. |
| sampled audit | predeclared sampling frame | sampled records and valid design | valid frame/design | unsampled population | “Estimated rate/interval in the stated sample frame”; no complete non-use claim. |
| institution-wide non-use | institution as a whole | unavailable under this contract | unavailable | all uninstrumented channels | **Claim unavailable.** |

## 12. Isolation and correction interface

The amendment does not define correction, notice, or supersession mechanics (`PAO-R36`); recovery,
retention, expiry, or durability (`OPS-R14`); or benchmark-oracle architecture (`S0-GAP-02`). The one
interface obligation survives: a corrected/superseding record may not carry a weaker individual-use
restriction than the predecessor. `PAO-R36` owns any mechanism.

## 13. Acceptance and falsification signals

Independent conformance may reconsider adoption only if the amended artifacts establish all of the
following without marker-only proof:

1. Artifact A is reclassified X and refused.
2. Artifact B is reclassified X and refused.
3. Artifact C is class G and is not refused merely for executability; it remains transport-only with
   no PolicyOS authority effect.
4. A false declared basis/completeness premise cannot produce a positive.
5. Scenario S-1 is outside the positive claim and cannot be used to assert institution-wide non-use.
6. Scenario S-2 remains blocked because observed consultation, not asserted counterfactual impact,
   turns the gate.
7. F-01 admits the planning request, then requires the real consumer-use gate to block silent
   eligibility drift; deleting that gate while retaining markers makes the fixture fail.
8. Every fixture contains one world, one detector, and one expected verdict.
9. Reference-class shopping, semantic-purpose synonyms, reliance laundering, and multi-hop relay have
   exact bounded outcomes.
10. No capability or canonical owner is upgraded by the amendment.

Until independent verification confirms those properties at an exact commit, the repository must not
claim that an operating individual-decision firewall exists or that the amended research is adopted.
