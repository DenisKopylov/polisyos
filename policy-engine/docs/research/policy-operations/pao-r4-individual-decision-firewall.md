---
title: PAO-R4 — Policy-to-Individual-Decision Firewall
research_id: PAO-R4
status: research
research_only: true
repository: DenisKopylov/polisyos
baseline_ref: main
baseline_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
result_standing: GO_WITH_REVISIONS
authoritative_for:
  - research definition of the population-to-individual semantic boundary
  - research-only handoff and detection semantics for policy exports
  - research-only disposition of inherently unsafe export classes
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

## 1. Result in one sentence

**A policy artifact may cross toward a case-management system only when its class is allow-listed,
its population meaning and declared basis remain attached, its denied individual uses travel
monotonically, the consumer binds a permitted purpose before receipt, and every use that cannot be
judged from the artifact alone is made observable through mandatory, content-bound returning
evidence; an individually actionable class for which those observables cannot be made complete is
not exportable.**

**Standing: `GO_WITH_REVISIONS`.** The narrow research contract is coherent and checkable. Revision
is required before any capability claim because the pinned repository has a live
`may_not_use_for` mechanism but no individual-decision vocabulary, no policy-to-case export gate,
and no complete returning-evidence chain. The strongest result is refusal: individually actionable
artifacts whose downstream use cannot be made observable must not cross.

This standing authorizes no implementation and makes no jurisdictional-compliance claim.

## 2. Scope and binding architecture

The identity decision assigns PolicyOS ownership of the **firewall**, while keeping the individual
determination outside PolicyOS: `policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:123-139@1a7a2d05ebba22fae80e9934329e4b880806588e`, finding **Individual-decision firewall**. The same
decision binds the anti-roles—PolicyOS is not an administrator, executor, case-management system,
court, notification channel, payment system, or CRM—at
`policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:88-91@1a7a2d05ebba22fae80e9934329e4b880806588e`.

The firewall therefore owns:

1. which PolicyOS artifact classes may leave toward a named case-system consumer;
2. which uses remain denied and how those denials survive derivation and projection;
3. what evidence of actual downstream use must return;
4. how absence, contradiction, or incompleteness limits PolicyOS's own claim about application.

It does **not** own the case-system workflow, individual fact finding, the legal or administrative
act, individual reasons, review, notification, payment, sanction, or remedy. That decomposition is
the four-way boundary test at
`policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:101-121@1a7a2d05ebba22fae80e9934329e4b880806588e`.

Three existing findings bind the design:

- **`S0-K05`**: observation, transport, or projection cannot create authority;
- **`S0-K07`**: projection cannot mint authority;
- **`S0-K11`**: protected actions require equivalent, action-specific protection.

They are ratified in
`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:96-112@1a7a2d05ebba22fae80e9934329e4b880806588e`.

**`PV-K04`** already supplies the monotonicity law: a projection may reduce detail but may not
amplify truth, certainty, authority, currency, or permission, and denied uses do not shrink
(`policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:138-146@1a7a2d05ebba22fae80e9934329e4b880806588e`). **`INT-K02`** supplies the basis law for every `delta`: the declared obligation set,
maintained assumptions, and relative-basis rider are part of the claim, not optional context
(`policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:117-126@1a7a2d05ebba22fae80e9934329e4b880806588e`).

## 3. Formal population/individual boundary

### 3.1 Objects

Let:

- \(\Omega\) be the universe of possible subjects;
- \(B\) be a declared claim basis containing population predicate, jurisdiction/geography, time,
  source and selection process, method, maintained assumptions, intended use, audience, and cutoff;
- \(C_B(x)\in\{0,1\}\) be the predicate assigning subject \(x\) to the reference class;
- \(R_B=\{x\in\Omega:C_B(x)=1\}\);
- \(D_B\) be the population data-generating or causal object licensed by \(B\);
- \(\Phi(D_B)=\theta\) be the population functional—mean, rate, distribution, treatment effect,
  calibrated group risk, elasticity, or another bounded population proposition;
- \(L\) be the limitations and denied-use set carried with the proposition.

A **population claim** is the tuple

\[
P=(R_B,B,\Phi,\theta,L)
\]

and asserts only that the named functional has the stated value or bounded relation under the
basis. Its quantifier ranges over a population distribution, reference class, or policy
counterfactual. It does not quantify over a particular person's administrative status.

For an identifiable or resolvable subject \(x\), an **individual determination claim** is a
proposition \(I_x=\psi(x,F_x,Q,A)\), where \(F_x\) are case facts, \(Q\) is the competent rule and
procedure, and \(A\) is the authority to make the protected determination. Examples are that \(x\)
is eligible, sanctionable, high risk, entitled to an amount, lower priority, not credible, selected
for investigation, or owed a particular reason.

### 3.2 Non-entailment

The firewall adopts the following semantic rule:

\[
P\land C_B(x)=1 \not\models I_x.
\]

Membership in the reference class makes arithmetic substitution possible; it does not make the
population proposition an individual fact. The entailment remains invalid unless a separately
admitted individual inference supplies, at minimum:

1. an individual estimand or decision target rather than a population functional;
2. a justified reference-class selection and transport relation for this person;
3. current, admissible case facts and treatment of missing or contradictory facts;
4. a competent individual decision rule and procedure;
5. authority for the protected action and its reason-giving/review safeguards.

Even when a model returns a number \(s(x)\), the number is not by itself eligibility, sanction,
risk authority, priority, credibility, or a case reason. Base rates constrain rational prediction,
but a base rate remains conditional on its reference class and does not determine the person's
state. Ecological association likewise does not establish an individual association.

### 3.3 Decidable individual use

An artifact \(a\) is **used for an individual decision** when all of the following are true:

1. a consumer resolves a natural person, household, firm, or other case subject \(x\), directly or
   through a stable/pseudonymous key;
2. the consumer performs or prepares a protected case action concerning \(x\);
3. information derived from \(a\) materially changes, supplies, defaults, ranks, thresholds,
   recommends, evidentially weights, explains, routes, or determines that action.

Material contribution is enough. The artifact need not be the sole input, and a human click does
not erase the use. The test is counterfactual and observable: holding the case facts and competent
rule fixed, would removing or changing the artifact alter the action, its order, its intensity, its
reason, or the evidence presented to the decision maker?

A **firewall violation** occurs when an exported artifact is used in that sense for a purpose in its
`may_not_use_for` set, or when a use requiring returning evidence occurs without complete,
trustworthy evidence. It is **silent** when no export gate, consumer gate, returning-evidence check,
or PolicyOS reconciliation produces a blocking, violation, or `not_established` verdict.

## 4. Handoff contract

### 4.1 Default and complete crossing rule

The default is refusal. An artifact may cross only if every predicate below is true:

1. **Class allow-list:** the artifact belongs to an enumerated crossing class.
2. **No subject resolution:** it contains no person/case row, subject key, resolvable pseudonym,
   individual score, or join path that makes a subject recoverable under the declared auxiliary
   information.
3. **Non-executability:** it does not contain a complete decision function, parameter vector,
   threshold table, or lookup surface that can be applied mechanically to a case.
4. **Basis preservation:** population, scope, selection, method, assumptions, cutoff, and limitations
   remain attached and source-resolvable.
5. **Monotone denial:** the exported `may_not_use_for` set is a superset of every source/derivation
   denial; no projection or summary removes a denied use.
6. **Purpose binding:** the named consumer declares and content-binds a permitted purpose before
   receiving the artifact.
7. **Composition safety:** the export is safe in the declared release history, not merely in
   isolation; an unknown history returns `not_established`.
8. **Returning evidence:** if compliance can be known only at use time, the consumer has a mandatory,
   complete, verifiable evidence obligation and its absence blocks the export or degrades the claim.

### 4.2 Crossing classes

| Class | Permitted form | Additional conditions | Required `may_not_use_for` effect |
|---|---|---|---|
| Aggregate descriptive statistic | Population/cohort aggregate with declared denominator and basis | No small-cell or auxiliary-information path to a subject; no row-level payload | Deny every individual-use purpose in §5 |
| Population causal or predictive estimate | Bounded population estimand, interval, or distribution | Estimand and transport limits visible; no individual scoring function or case threshold | Deny individual prediction, ranking, eligibility, sanction, amount, reasons, and final determination |
| General rule statement | Normative or policy-level statement without executable parameters | No complete thresholds, parameter table, code, or per-case lookup | Deny case application, reason generation, evidence weighting, and final determination |
| Cohort allocation or operational envelope | Non-singleton planning envelope | Cohort remains non-resolvable under composition; used only for programme planning | Deny individual priority, routing, amount, service access, review intensity, and enforcement |
| Synthetic exemplar | Non-resolvable, explicitly synthetic example | Cannot correspond to or be joined to a real subject; training/communication purpose bound | Deny all real-case use and any representation as evidence about a real person |

“Anonymized” is not an independent permission class. It is an empirical claim about resistance to
resolution under stated auxiliary information and composition. If that claim is not established,
the artifact is treated as person-resolvable and refused.

### 4.3 Inherently unsafe classes—refuse export

The following classes cannot safely cross toward case systems under the research contract:

- person-level, household-level, firm-level, case-level, pseudonymized, or purportedly anonymized
  rows that remain resolvable or joinable;
- individual scores, labels, rankings, watchlists, propensities, flags, or recommendations;
- executable rules, complete parameter vectors, threshold tables, decision trees, or lookup tables
  usable against case facts;
- small-cell or multi-export artifacts for which composition safety is not proved over the complete
  release history;
- subject-binding keys, resolvers, or deterministic mappings from case facts to a decision output;
- any class whose compliance with denied individual uses can be inferred only from voluntary or
  unverifiable downstream reporting.

For these classes no downstream policy text cures the observability problem. Exporting them creates
a possible prohibited use for which PolicyOS cannot distinguish compliance from silence.

## 5. Prohibited-individual-use matrix

Every permitted crossing carries, at minimum, the following denied purposes. The vocabulary extends
the existing `may_not_use_for` mechanism; it does not replace or weaken existing terms.

| Denied purpose | Protected effect | Why population evidence is insufficient |
|---|---|---|
| `individual_eligibility_determination` | Access to a benefit, licence, status, or programme | Class membership or group rate does not establish the person's rule-satisfying facts |
| `individual_benefit_or_burden_amount` | Amount paid, charged, withheld, recovered, or allocated | A population response or average does not determine the lawful individual amount |
| `individual_sanction_or_enforcement` | Penalty, inspection, enforcement, exclusion, or adverse action | Statistical generalization cannot replace case proof and competent discretion |
| `individual_risk_scoring_or_profiling` | Risk label, score, propensity, or profile | A base rate is reference-class conditional and is not an individual state |
| `individual_priority_or_triage` | Queue order, urgency, scarce-resource priority | Group effects do not justify the person's relative rank |
| `individual_investigation_or_surveillance_targeting` | Selection for scrutiny, audit, investigation, or monitoring | Population association cannot furnish individualized suspicion or necessity |
| `individual_credibility_fraud_or_integrity_assessment` | Credibility, fraud, honesty, or integrity inference | Group statistics cannot establish a person's conduct or credibility |
| `individual_service_access_or_routing` | Channel, service level, referral, or denial of human access | Aggregate efficiency cannot decide the person's service route |
| `individual_evidence_weighting_or_adverse_inference` | Weight assigned to case evidence or inference from absence | Population evidence cannot silently alter the adjudicative record |
| `individual_reason_generation` | Stated grounds for an individual act | A population explanation is not the actual case-specific ground |
| `individual_human_review_selection_or_intensity` | Whether and how much human review occurs | Human review cannot be rationed using the same ungrounded individual inference |
| `individual_recommendation_materially_affecting_rights` | Recommendation strongly relied on for a protected action | Formal finality is irrelevant when the recommendation materially drives the result |
| `case_closeout_or_final_determination` | Closing, approving, denying, or otherwise determining the case | PolicyOS has no case authority and population output cannot mint it |

A human remains responsible for the individual act, but “human in the loop” is not a firewall
verdict. The gate remains red when the artifact materially contributes to a denied purpose.

## 6. Detection semantics

### 6.1 Export-time detectable

The exporter can decide the following from the artifact, its provenance, the request, and the
controlled release history:

- a person/case row, identifier, pseudonym, subject resolver, or join key is present;
- cell size or uniqueness violates the declared non-resolution condition;
- a rule is complete enough to execute against case facts;
- an individual score, label, rank, threshold, recommendation, or watchlist is present;
- basis, limitations, purpose, consumer, or mandatory evidence terms are missing;
- a derivation or projection removed a denied use;
- the proposed export, combined with prior controlled exports, crosses a declared reconstruction
  boundary;
- the release history or auxiliary-information model is incomplete, producing `not_established`.

The output is one of `ALLOW_NON_INDIVIDUAL`, `REFUSE_EXPORT`, `BLOCK_PURPOSE`,
`BLOCK_PERMISSION_AMPLIFICATION`, `BLOCK_COMPOSITION`, or `NOT_ESTABLISHED`. A marker-only check is
insufficient; the gate must evaluate the actual artifact and derivation.

### 6.2 Detectable only at use time

The artifact alone cannot establish whether a downstream operator later uses it to determine
eligibility, amount, sanction, risk, priority, investigation, credibility, service route, evidence
weight, reasons, review intensity, recommendation, or closeout. Those facts exist in a system
PolicyOS does not control. They become visible only if the consumer:

1. declares the use before receiving or invoking the artifact;
2. evaluates the denied-use set at the point of material contribution;
3. records every use attempt and every protected case action in a complete denominator;
4. returns evidence that can be reconciled against the issued artifact and case-event totals.

The consumer-side verdict must be `BLOCK_PURPOSE` for a denied use. A permitted use returns a
bounded receipt; it does not turn the artifact into case authority.

### 6.3 Not detectable at all under an incomplete boundary

The following are observationally indistinguishable from compliant non-use unless a broader,
mandatory evidence boundary is established:

- an operator reads a report and manually applies or memorizes the rule off ledger;
- a screenshot, transcription, copied number, or uncontrolled derivative is used;
- an external join resolves a subject outside the declared auxiliary-information model;
- a sequence of individually compliant queries reconstructs a case rule while no complete transcript
  is available;
- the consumer omits, falsifies, or selectively reports use evidence;
- a downstream system exports the artifact again without preserving restrictions and lineage.

For an artifact class that remains individually actionable under any of these paths, **refusal is
the only enforceable firewall result**. Calling such a prohibition a firewall would otherwise be a
claim about an unobservable fact.

## 7. Returning-evidence interface—semantics, not a schema

The returning channel is the only way PolicyOS can learn how its policy artifact was actually
applied. It has four semantic layers.

### 7.1 Issue evidence

For every crossing, PolicyOS retains the artifact and derivation digest, complete denied-use set,
declared permitted purpose, named consumer/system boundary, basis and rule versions, issue time,
and release-history position.

### 7.2 Use evidence

For every import, derivation, use attempt, and protected case action inside the declared consumer
boundary, the case system reports:

- the exact artifact or derived-artifact digest;
- declared purpose and protected action class;
- a scoped pseudonymous subject reference sufficient for reconciliation but not public identity;
- decision stage and whether the artifact was displayed, invoked, thresholded, ranked, or otherwise
  materially relied upon;
- consumer-gate verdict and reasons;
- human role, override, and whether removing the artifact would have changed the action;
- outcome/reason reference, consumer version, and event time.

This list states meaning only. It does not ratify a wire representation or case-system data model.

### 7.3 Completeness and trust

A positive firewall claim requires complete denominators for issued artifacts, downstream imports,
derivations, use attempts, and protected case actions in the declared integration boundary. Evidence
must resolve to committed records, content-bind to the artifact and case event, carry non-producer
verifier provenance where a verification claim is made, be append-only, and reconcile against
independent case-event totals or another competent source.

Missing, late, contradictory, unresolved, selectively sampled, or self-attested-only evidence does
not mean “no prohibited use.” It means `FIREWALL_CLAIM_NOT_ESTABLISHED`; where the use is protected,
the affected action or export fails closed.

### 7.4 Voluntary reporting

A voluntary channel cannot support a firewall claim. The observations under “compliant non-use” and
“prohibited use followed by silence” are identical. Voluntary reporting therefore reduces the
contract to a documented restriction or terms-of-use statement. Any class needing use-time detection
must be refused until reporting and reconciliation are mandatory and trustworthy.

## 8. Comparative selection

The selected design is a composition, not a single control:

- artifact-class allow-list;
- form and resolution transformation gates;
- provenance-carried, monotone `may_not_use_for` restrictions;
- request-time purpose binding;
- consumer-side enforcement;
- mandatory returning evidence with reconciliation;
- refusal for classes whose use cannot be made observable.

Human review is a safeguard inside an individual-decision regime, not the policy-to-individual
boundary. Export-permissive audit is rejected because it detects only after harm and treats absent
reports as benign. The complete comparison and eliminating properties are in
`pao-r4/comparative-models.md`.

## 9. Legal and administrative-law transfer

The external regimes do not supply a PolicyOS compliance conclusion. They establish transferable
boundary principles:

- EU data-protection law distinguishes certain solely automated significant decisions and requires
  safeguards; the CJEU has held that a score may be part of such decision-making where a third party
  draws strongly on it.
- EU administrative-rights sources protect hearing, file access, and reason-giving in their own
  scopes.
- Canada's federal automated-decision directive uses notice, explanation, testing, monitoring,
  intervention, and recourse measures scaled to impact.
- United States administrative procedure requires notice and brief grounds for certain denials, and
  anti-discrimination doctrine rejects class averages as a substitute for treatment of the person.

PAO-R4 is not weaker where those lines are narrower: it treats **material contribution**, not only
formal finality or sole automation, as firewall-relevant; it does not rely on a human rubber stamp;
and it refuses individually actionable classes when actual use cannot be observed. Details and
stable identifiers are in the external-source ledger.

## 10. Repository standing and dependencies

At the pin, `may_not_use_for` is live and consumer-enforced in bounded owners, and public projection
already carries denials. But `individual_decision`, `export_gate`, and `prohibited_use` appear in
zero files below `policy-engine/src`; the firewall vocabulary and chain are absent. The accurate
state for PAO-R4's new capabilities is **absent/unallocated**, not `contract_only`,
`producer_missing`, `bridge_missing`, or `verification_missing`. The evidence for every label is in
`pao-r4/repository-integration-handoff.md`.

The work is isolated from the wave-4 siblings. It does not define correction or supersession
mechanics (`PAO-R36`), durability/recovery/retention/expiry (`OPS-R14`), or benchmark oracles
(`S0-GAP-02`). One interface obligation crosses the boundary: a corrected/superseding record must
not carry a weaker individual-use restriction than its predecessor. `PAO-R36` owns the mechanism.

## 11. Acceptance signal

The commission's falsifier is closed only when a policy-level statistical rule presented for
individual eligibility produces a red consumer gate and a reconciled violation record. More
broadly, acceptance requires all of the following:

1. the complete crossing allow-list and denied-purpose vocabulary have accepted owners;
2. every export and derivation preserves the basis and union of denied uses;
3. individually executable or resolvable classes are refused;
4. every use-time-only protected action passes a mandatory consumer gate;
5. returning evidence is complete, content-bound, verifiable, and reconciled;
6. absent evidence produces `not_established`, never compliance;
7. the falsifier suite passes against the real export and consumer paths.

Until then, the repository must not claim that an individual-decision firewall exists.
