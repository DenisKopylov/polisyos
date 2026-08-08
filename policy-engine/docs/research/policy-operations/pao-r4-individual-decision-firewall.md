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
refused merely because it is executable: it may travel as rule-level input under an external
authority's own fact-finding and procedure, without becoming PolicyOS case authority.**

**Research standing remains `GO_WITH_REVISIONS`; adoption remains `NO_GO` pending independent
conformance verification.** The amendment does not claim implementation. The repository still lacks
the individual-use vocabulary, policy-to-case gate, governed external consumer, complete returning-
evidence chain, and composition transcript required for a capability claim.

The positive firewall proposition is bounded:

> Within a named governed integration boundary, and only for events and channels whose complete
> denominators are independently reconciled, the contract can establish that every recorded
> protected-action consultation was permitted or blocked. It cannot establish institution-wide
> non-use, human memory, off-ledger copies, or activity outside that boundary.

## 2. Scope and binding architecture

The identity ruling assigns PolicyOS ownership of the **individual-decision firewall**, while the
individual determination remains external:
`policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:123-139@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, finding **Individual-decision firewall**. The
binding anti-roles remain at `:88-91`: PolicyOS is not an administrator, executor, case-management
system, court, notification channel, payment system, or CRM.

The firewall owns:

1. which semantic classes may cross toward a named consumer;
2. which uses remain denied and how denials survive derivation, projection, and correction;
3. what observable makes downstream individual use visible;
4. what evidence returns and which bounded claim it supports; and
5. when refusal or `NOT_ESTABLISHED` is the only honest result.

It does not own case fact finding, legal applicability, competent authority, the administrative act,
individual reasons, review, notification, payment, sanction, remedy, or case workflow.

The amendment consumes, rather than re-authors:

- **`S0-K05`** — observation, transport, or projection cannot create authority;
- **`S0-K07`** — projection cannot mint authority;
- **`S0-K11`** — protected actions require equivalent, action-specific protection;
- **`PV-K04`** — projection may reduce detail but may not amplify authority or permission, and denied
  uses do not shrink; and
- **`INT-K02`** — a `delta` is inseparable from its obligation basis and assumptions; PAO-R4 transfers
  the bounded lesson that an empirical claim stripped of its basis changes meaning.

The amendment also applies:

- **`P35`** — every set-level fact names path and file-type denominators;
- **`P36`** — adjacency does not appoint an owner; and
- **`P37`** — every gate predicate has a frozen provenance class, and a merely asserted,
  institutionally supplied, or unestablished predicate cannot yield an authority-grade positive.

See
`policy-engine/docs/reference/policy-design-case-failure-patterns.md:79-81@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`.

## 3. Formal population/individual boundary

### 3.1 Four semantic classes

Classification is semantic and compositional, never controlled by a filename, field name, or an
“aggregate,” “rule,” or “synthetic” label.

#### E — empirical population summary, probability, or effect

Let:

- \(\Omega\) be the subject universe under declared identity, time, jurisdiction, and tenant scope;
- \(B\) be the empirical basis: population predicate, geography/jurisdiction, time, source and
  selection process, method, maintained assumptions, intended use, audience, and cutoff;
- \(C_B(x)\in\{0,1\}\) assign subject \(x\) to the reference class;
- \(R_B=\{x\in\Omega:C_B(x)=1\}\);
- \(D_B\) be the data-generating or causal object identified under \(B\);
- \(\Phi\) be a population functional such as a mean, rate, distribution, treatment effect,
  calibrated group risk, or elasticity;
- \(\theta=\Phi(D_B)\); and
- \(L\) be limitations and denied uses.

The empirical population claim is

\[
P_E=(R_B,B,D_B,\Phi,\theta,L).
\]

Its quantifier and estimand are population-level. It is not a normative rule and does not itself say
what a competent body must do to a person.

#### G — normative general rule under an external competent authority

A normative rule is a different object:

\[
G=(A_G,J_G,T_G,Q_G,\Gamma_G,L_G),
\]

where \(A_G\) is an externally supplied authority claim, \(J_G\) and \(T_G\) are jurisdiction and
time, \(Q_G\) is the rule predicate applied to case facts, \(\Gamma_G\) is the normative consequence,
and \(L_G\) contains limitations and denied uses.

PAO-R4 does not determine whether \(A_G\) is competent or \(Q_G\) is satisfied in a case. A normative
rule may intentionally be applicable to a person:

\[
G\land Q_G(F_x)\models \Gamma_G(x).
\]

That is rule application, not ecological inference. Transporting \(G\) does not make PolicyOS the
case authority and does not establish validity, applicability, legal sufficiency, or an individual
determination.

#### X — individual or pointwise-recoverable artifact

An artifact is X when, under the permitted history and auxiliary-information model, it resolves a
subject or supplies a pointwise mapping capable of determining or materially constraining a protected
action. Person rows, individual scores, singleton aggregates, deterministic partitions, differencing
query families, rankings, watchlists, and final case recommendations are examples.

#### S — synthetic non-case example

An S artifact is explicitly synthetic and remains non-resolvable to any real subject under the named
history and auxiliary model. A real-subject match reclassifies it as X.

Unknown or mixed class returns `NOT_ESTABLISHED`; it is refused for a protected case-system handoff.

### 3.2 Empirical non-entailment

For E that is not pointwise recoverable under the admitted history:

\[
P_E\land C_B(x)=1\not\models F_x
\]

and therefore

\[
P_E\land C_B(x)=1\not\models I_x,
\]

where \(F_x\) are individual case facts and
\(I_x=\psi(x,F_x,G,A,P)\) is an individual determination under a competent rule \(G\), authority
\(A\), and procedure \(P\).

Membership permits arithmetic substitution; it does not establish outcome, eligibility,
sanctionability, risk state, priority, credibility, reason, or entitlement. A calibrated probability
remains probabilistic, and an ecological relation remains aggregate. A separate individual inference
would require an individual target, justified reference-class and transport relation, current case
facts, treatment of missing or contradictory facts, a competent normative rule and procedure, and
authority for the action. PAO-R4 supplies none of those merely by exporting \(P_E\).

This non-entailment does **not** govern G. The original formalism did not admit normative rules into
\(P_E\); the defect was that the original crossing/refusal sections nevertheless grouped general
rules with empirical estimates and refused executability. Sections 3 and 4 now agree.

### 3.3 Pointwise recoverability

For artifact \(a\) and named permitted history/auxiliary model \(H\):

\[
\operatorname{individualizable}(a,H)=1
\]

iff there exists a resolvable subject \(x\) such that \(a,H\) reveal an individual fact or supply a
pointwise mapping that determines or materially constrains a protected action for \(x\).

- E with `individualizable(a,H)=1` is reclassified X and refused for protected crossing.
- S that becomes resolvable is reclassified X.
- G may be individually applicable and is not refused merely for that or for executability. It may
  travel as rule-level input with no PolicyOS authority effect; authority and applicability remain
  institutionally supplied and `NOT_ESTABLISHED` to PolicyOS.
- Unknown semantic class or incomplete \(H\) returns `NOT_ESTABLISHED` and refuses protected crossing.

The audit artifacts close as follows:

| Audit artifact | Semantic result | Authority-gate result |
|---|---|---|
| A — singleton empirical rate | E becomes X because it resolves one person and reveals the outcome | `REFUSE_EXPORT` |
| B — deterministic empirical partition | E becomes X because the family is a pointwise decision surface | `REFUSE_EXPORT` |
| C — normative universal rule | G; executability is expected and candidate-band rule transport is not blocked | authority/applicability `NOT_ESTABLISHED`; `REFUSE_EXPORT` is forbidden solely on executability grounds |

No new product outcome-vocabulary element is created for G transport. The statement is a bounded
candidate/authority distinction, not a new status.

### 3.4 Observable individual use

Inside the declared governed integration boundary, the conservative rule is:

> A PolicyOS artifact or derivative is **used** in a protected individual action whenever the
> instrumented case process consults, displays, queries, invokes, supplies, thresholds, ranks,
> recommends from, evidentially weights, explains with, or routes by it while a subject and protected
> action are resolved.

Consultation is enough. The consumer is not asked whether the action “would have changed.” This
accepts boundary false positives rather than silent false negatives. A counterfactual effect estimate
may support a narrower analytical claim only when independently validated; an operator answer is
`consumer_asserted` and cannot make a gate green.

A violation occurs when consultation is for a denied use, when E/X fills an individual fact or
authority slot, when G is represented as PolicyOS's determination/authority, or when mandatory
evidence is absent. It is silent when no export-context gate, consumer-use gate, evidence
reconciliation, or `NOT_ESTABLISHED` result becomes visible.

Residual false negatives include prior memory, screenshots, off-ledger reading, hidden local models,
and other uninstrumented channels. They are outside the positive claim and may force refusal of an
actionable class.

### 3.5 `P37` predicate-provenance table

Every load-bearing predicate receives exactly one frozen provenance class at admission:

`recomputed` · `independently_reconciled` · `consumer_asserted` ·
`institutionally_supplied` · `not_established`.

The last three cannot yield an authority-grade positive. They fail closed for the protected action or
downgrade the claim to candidate transport/observation only.

| Gate predicate | Required input | Required provenance for a positive | Asserted/supplied/unknown result |
|---|---|---|---|
| artifact bytes, digest, declared fields | canonical artifact and parser | `recomputed` | malformed/unresolved → `NOT_ESTABLISHED` |
| source/derivation denied-use union | complete controlled lineage | `recomputed` | incomplete lineage → `NOT_ESTABLISHED` |
| registered basis-field presence | basis obligations + artifact | `recomputed` | missing → `BLOCK_BASIS` |
| truth/completeness of \(B,L\) | independent source/obligation evidence | `independently_reconciled` | declaration alone cannot produce a positive |
| E/G/X/S semantic class | content and source identity | `recomputed` plus source identity `independently_reconciled` | external competence stays `institutionally_supplied`; authority remains unavailable |
| completeness of \(H\) | release/query transcript + independent inventory | `independently_reconciled` | incomplete/narrow model → `NOT_ESTABLISHED` |
| `individualizable(a,H)` | artifact, behavioral interpreter, complete \(H\) | `recomputed` | incomplete \(H\) → `NOT_ESTABLISHED`/refuse |
| request purpose | request record | `consumer_asserted` only | can block an open denial; cannot prove later use |
| protected-action effect | action event + canonical effect mapping | `recomputed` or `independently_reconciled` | benign label alone → `NOT_ESTABLISHED` |
| consultation/invocation | instrumented data-flow event | `recomputed` | absent instrumentation → outside boundary/no complete claim |
| protected-action denominator | independent event totals | `independently_reconciled` | consumer total alone → no complete non-use claim |
| “would the action change?” | validated removal experiment/independent causal evidence | `independently_reconciled` | operator answer is `consumer_asserted`; cannot make gate green |
| G authority/applicability | competent institution and external procedure | `institutionally_supplied` | candidate rule transport may remain unblocked; no authority/compliance positive |

#### Falsify-the-declaration probes

- Keep a “complete basis” declaration while omitting a material assumption: field presence is green,
  semantic completeness is not reconciled, so the result is `NOT_ESTABLISHED`.
- Scenario S-1: all in-boundary records reconcile while an operator later relies on remembered data
  outside instrumentation. The bounded receipt may remain true; institution-wide non-use is
  unavailable.
- Scenario S-2: the operator asserts immateriality while an instrumented display occurred. The
  consultation rule still turns the denied-use gate.

## 4. Handoff contract

### 4.1 Authority-band rule

The Stage-0 authority-band lens is controlling:
`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:46-88@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, with the binding application note at `:164-176`.
A prohibition may bind what is claimed or treated as determinative in the authority band. It must not
prohibit candidate computation or transport merely because an artifact is executable.

A predicate over **executability** would forbid PolicyOS from exporting its own governed core output:
the obligation/admissibility calculus itself computes case-relevant obligations from rules.
Executability is a candidate-band property. The firewall binds **authority to determine**, empirical
individualization, and unobservable prohibited use.

### 4.2 Crossing classes and forms

| Class | Permitted crossing form | Conditions | Denied-use effect |
|---|---|---|---|
| E | population aggregate, interval, distribution, or policy estimate | `individualizable(a,H)=0` under reconciled \(H\); visible basis; non-individual purpose | deny every individual-use purpose in §5 |
| G | rule-level input, including executable parameters needed to express the rule | source identity reconciled; external authority/applicability remains external; PolicyOS supplies no case facts, reasons, procedure, or final act | deny representation as PolicyOS determination, reason, fact finding, or authority grant |
| X | no governed protected-action crossing | candidate research/computation is not forbidden | refuse protected crossing |
| S | non-resolvable synthetic example | `individualizable(a,H)=0`; no real-case mapping | deny all real-case use |
| unknown/mixed | none for protected handoff | class or decisive predicate unavailable | `NOT_ESTABLISHED` and refuse |

“Anonymized” is an empirical proposition about resistance to resolution under named \(H\), not an
independent permission word.

### 4.3 Complete crossing predicates

A bounded positive requires every decisive predicate to be recomputed or independently reconciled:

1. semantic class established;
2. artifact/lineage resolved and basis obligations present;
3. source/derivation denied-use union preserved under `PV-K04`;
4. named \(H\) inventory complete for the claim;
5. E/S not individualizable under \(H\);
6. consumer and request purpose recorded without treating the declaration as use proof;
7. every protected-action consultation routed through the consumer gate;
8. imports, derivatives, consultations, attempts, and protected actions independently reconciled; and
9. claim wording remains within §11.

G may remain candidate-transportable with an explicit external premise, but its authority,
applicability, and individual determination remain `NOT_ESTABLISHED` to PolicyOS.

### 4.4 Authority-scoped refusal frontier

Refuse protected crossing when:

- E/S is subject-resolvable or pointwise-recoverable under \(H\);
- an empirical score, rank, propensity, watchlist, recommendation, deterministic partition, or query
  family can fill a protected individual slot;
- a person/case row, stable pseudonym, resolver, or case-binding key crosses;
- small-cell or multi-export composition is unsafe or history is incomplete;
- an unknown/mixed artifact cannot be distinguished from empirical individualization;
- G is presented as PolicyOS's determination, reason, fact, or authority rather than external
  rule-level input;
- denied uses shrink through projection, derivation, correction, or relay;
- use can be known only through voluntary, sampled, self-attested, or unverifiable reporting; or
- a material off-ledger route remains for an individually actionable artifact.

Artifact C is not refused merely for executability. An empirical decision tree with identical syntax
is X and is refused because its semantic class and authority effect differ.

## 5. Prohibited individual-use matrix

Every E/S crossing carries at least these `may_not_use_for` purposes. G additionally denies any
representation that PolicyOS supplied external authority, case facts, reasons, or the final act.

| Denied purpose | Protected effect | Why E is insufficient |
|---|---|---|
| `individual_eligibility_determination` | benefit/licence/status/programme access | reference-class membership does not establish rule-satisfying facts |
| `individual_benefit_or_burden_amount` | payment, charge, withholding, recovery, allocation | population response does not determine lawful individual amount |
| `individual_sanction_or_enforcement` | penalty, inspection, exclusion, adverse action | statistical generalization cannot replace case proof/procedure |
| `individual_risk_scoring_or_profiling` | risk label, score, propensity, profile | base rate is conditional, not an individual state |
| `individual_priority_or_triage` | queue, urgency, scarce-resource rank | group effects do not establish relative rank |
| `individual_investigation_or_surveillance_targeting` | scrutiny, audit, investigation, monitoring | association is not individualized suspicion/necessity |
| `individual_credibility_fraud_or_integrity_assessment` | credibility, fraud, honesty, integrity | group statistics do not prove conduct |
| `individual_service_access_or_routing` | channel, service level, referral, human access | aggregate efficiency does not decide the route |
| `individual_evidence_weighting_or_adverse_inference` | case-evidence weight or adverse inference | population evidence cannot silently alter the record |
| `individual_reason_generation` | grounds for an individual act | population explanation is not case-specific ground |
| `individual_human_review_selection_or_intensity` | whether/how much review | review cannot be rationed by the same inference |
| `individual_recommendation_materially_affecting_rights` | recommendation used in protected action | formal finality does not erase consultation |
| `case_closeout_or_final_determination` | approve, deny, close, determine | transport cannot mint case authority |
| `policyos_as_case_rule_authority` | representation that PolicyOS validated/owns external rule authority | PolicyOS owns the firewall, not the sovereign function |

A human click does not cure a denied use. Instrumented consultation is enough to trigger the gate.

## 6. Detection semantics — four locations

### 6.1 Artifact-local observable

| Predicate | Input | False/incomplete verdict |
|---|---|---|
| explicit case row/key | artifact and parser | `REFUSE_EXPORT` |
| individual score/rank/watchlist/recommendation | artifact semantics | `REFUSE_EXPORT` |
| registered basis field absent | obligations + artifact | `BLOCK_BASIS` |
| denied use shrank from resolved source | controlled lineage | `BLOCK_PERMISSION_AMPLIFICATION` |
| artifact/lineage cannot resolve | references/registry | `NOT_ESTABLISHED` |

Artifact inspection cannot prove that no material assumption was omitted.

### 6.2 Export-context observable with named \(H\)

| Predicate | Required context | Incomplete verdict |
|---|---|---|
| joins/singletons resolve a subject | \(H\), population inventory, linkage model | `NOT_ESTABLISHED`; refuse |
| deterministic/pointwise recovery | artifact family, behavioral interpreter, case-feature domain | `NOT_ESTABLISHED`; refuse |
| composition across exports/queries | complete transcript and release-family identity | unsafe → `BLOCK_COMPOSITION`; unknown → `NOT_ESTABLISHED` |
| E/G/X/S class | content, source identity, authority provenance | unknown/mixed → `NOT_ESTABLISHED` |
| semantic basis completeness | independent obligation/source reconciliation | declaration alone → no positive |

### 6.3 Downstream use-context observable

The governed consumer receives resolved subject, protected-action effect, exact artifact/derivative
digest, and consultation event. A denied consultation returns `BLOCK_PURPOSE` before action. A bypass
returns `FIREWALL_VIOLATION`. Purpose synonyms are resolved from action effects, not trusted strings.

The return path reconciles issued artifacts, imports, derivatives, consultations, verdicts,
bypasses, protected-action totals, boundary, and interval. Incomplete instrumentation or denominator
means no complete positive.

### 6.4 Outside the declared boundary — not observable

Memory, screenshots, transcription, hidden local models, outside-transcript reference-class shopping,
outside-mapping purpose relabeling, lineage-stripped relays, unmodelled joins, and reports beyond
independent reconciliation remain outside the positive claim. An actionable artifact with a material
route through them is refused. Complete in-boundary evidence never establishes institution-wide
non-use.

## 7. Returning-evidence interface — semantics, not schema

### 7.1 Issue evidence

Retain exact artifact/derivation digest, semantic class, source basis and obligation identity, denied-
use union, consumer, permitted request purpose, boundary, \(H\), issue time, and history position.

### 7.2 Use evidence

For every import, derivative, consultation, gate attempt, and protected action, return:

- artifact/derivative digests and lineage;
- scoped subject reference;
- protected-action effect, not only a purpose string;
- instrumented consultation and stage;
- verdict and reason;
- human role/override;
- outcome/reason reference, consumer version, event time; and
- frozen predicate-provenance classes.

This is semantic content, not a wire, API, database, or case-system model.

### 7.3 Trust and completeness

A complete in-boundary claim requires content-bound committed records, append-only history,
complete derivative lineage, independently reconciled consultation/action denominators, non-producer
verification where claimed, and fail-closed treatment of missing, late, contradictory, sampled,
unresolved, or self-attested evidence.

Failure yields `FIREWALL_CLAIM_NOT_ESTABLISHED`; it never means no use. Content binding proves what
was recorded, not a counterfactual's truth. Scenario S-2 is closed by consultation as the gate
predicate.

### 7.4 Voluntary reporting and bounded claim lattice

The impossibility remains:

```text
world A: no prohibited use; no report
world B: prohibited use; no report
observation: identical
```

Voluntary reporting cannot establish a **complete non-use firewall claim**. A class requiring use-
time detection is refused until reporting and reconciliation are mandatory and trustworthy.

| Evidence posture | Maximum supported claim |
|---|---|
| no voluntary reports | no non-use inference; documented restriction only |
| content-bound voluntary reports | observed incidents; no completeness claim |
| known denominator with incomplete participation | lower bound on observed prohibited uses |
| valid predeclared sampled audit | sampled rate/interval for that frame |
| mandatory complete independently reconciled boundary | bounded in-boundary complete-use/non-use claim, subject to residual channels |

These are claim bounds under `INT-K08`, not a new outcome/status vocabulary.

## 8. Comparative selection

The selected architecture combines semantic classes, artifact-local checks, named-\(H\) export
checks, monotone restrictions under `PV-K04`, request-purpose recording without use inference,
conservative consultation gating, mandatory reconciled evidence, and refusal when empirical/pointwise
prohibited use cannot be observed.

Human review is an external safeguard, not the firewall. Permissive audit is insufficient.
Executability alone is not a rejection criterion; semantic class and authority effect are.

## 9. Legal and administrative-law transfer

The cited regimes supply comparative principles, not compliance conclusions. PAO-R4 is **not
narrower on the material-reliance/formal-finality trigger** than sole-automation or formal-decision
comparators: upstream material consultation and human-mediated use remain inside the engineering
gate. This does not compare or replace full rights, duties, exceptions, remedies, competence,
hearing, explanation, or review.

The external-source ledger pins mutable sources, identifies currentness, labels inference, and keeps
every non-transfer limit.

## 10. Repository standing, census, and owner placement

The supplied complete census is recorded in the orientation ledger:

- `may_not_use_for`: 106 Python files, 794 matching lines, 903 occurrences;
- disjoint partition: 67 runtime, 12 scientist, 27 remainder;
- `aggregate_only`: seven all-source files;
- case-insensitive `anonymi`: seven all-source and six Python files; and
- exact `individual_decision`, `export_gate`, `prohibited_use`: zero files, lines, and occurrences.

The source has a pervasive denied-use carrier but no PAO-R4 concept or gate. The capability remains
**`absent/unallocated`**.

Core authority envelopes/consumers are established denied-use owners and projection semantics is the
established denial-monotonicity owner. `public_export.py` is a public-bundle producer, but no pinned
finding makes it the canonical owner of every purpose-bound case-system handoff. The emission
chokepoint is an **open consolidation decision**; this research appoints nobody.

## 11. Claim-boundary table

| Claim subject | Boundary | Observable | Completeness premise | Residual | Exact allowed wording |
|---|---|---|---|---|---|
| E non-entailment | empirical semantics | class, estimand, basis, no pointwise recovery under \(H\) | class/\(H\) recomputed/reconciled | unmodelled auxiliary data | “This empirical population claim does not by itself establish the person's facts or determination.” |
| G transport | issue boundary | source identity, content, restrictions | source identity reconciled; authority/applicability external | invalid/inapplicable rule | “Rule-level input transported with no PolicyOS authority effect; applicability not established by PolicyOS.” |
| X refusal | export-context | subject resolution/pointwise mapping | \(H\) sufficient for refusal witness | other unresolved routes | “Protected crossing refused because the artifact is individualizable.” |
| S transport | issue boundary | synthetic provenance/non-resolution | \(H\) reconciled | unknown linkage | “Synthetic non-case example within the named model; no real-case use permitted.” |
| denial preservation | governed lineage | resolved lineage/set union | complete controlled lineage | uncontrolled copy | “All known source/derivation denials are preserved in this chain.” |
| consultation control | named consumer and interval | consultation, verdict, action denominator | mandatory instrumentation/reconciliation | memory/off-ledger/relay | “Every recorded protected-action consultation in boundary B during T was gated and reconciled.” |
| complete non-use | mandatory reconciled boundary only | complete imports, derivatives, consultations, actions | independent complete denominators | outside-boundary channels | “No prohibited consultation was observed within the declared complete boundary”; never “no use anywhere.” |
| voluntary reports | participants only | received reports | no completeness premise | non-reporting uses | “N prohibited uses were reported”; no non-use inference. |
| sampled audit | predeclared frame | sampled records/design | valid frame/design | unsampled population | “Estimated rate/interval in the stated frame”; no complete non-use claim. |
| institution-wide non-use | whole institution | unavailable | unavailable | uninstrumented channels | **Claim unavailable.** |

## 12. Isolation and correction interface

The amendment defines no correction/notice/supersession mechanics (`PAO-R36`), durability/recovery/
retention/expiry (`OPS-R14`), or benchmark-oracle architecture (`S0-GAP-02`). The sole interface
obligation remains: a corrected/superseding record may not carry a weaker individual-use restriction
than its predecessor. `PAO-R36` owns any mechanism.

## 13. Acceptance and falsification signals

Independent conformance may reconsider adoption only when:

1. A and B are reclassified X and refused;
2. C is G, candidate rule transport is not blocked merely for executability, and authority/
   applicability remain `NOT_ESTABLISHED`;
3. the identical-syntax empirical decision tree is refused;
4. false basis/completeness declarations cannot yield a positive;
5. S-1 is outside the positive claim;
6. S-2 remains blocked by observed consultation;
7. F-01 admits planning then requires the real consumer-use gate, and deleting that behavior while
   retaining markers fails;
8. every fixture has one world, detector, and expected verdict;
9. reference-class shopping, purpose synonyms, reliance laundering, and relay have bounded results;
10. no capability, outcome vocabulary, or canonical owner is upgraded.

Until an independent verifier confirms these properties at an exact commit, the repository must not
claim an operating firewall or adoption of the amendment.
