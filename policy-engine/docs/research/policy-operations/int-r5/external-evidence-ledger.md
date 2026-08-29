# INT-R5 External Evidence Ledger

## 1. Status and use restriction

This ledger transfers findings from the five commissioned deep-research surveys into INT-R5. The
surveys are **external practice evidence**. They are not repository capability, legal advice,
registered PolicyOS vocabulary, an institutional appointment or authority to implement.

Each transferred rule is labelled as one of:

- **legal rule in a named jurisdiction/regime**;
- **formal or technical mechanism**;
- **control/design pattern**;
- **empirical finding**;
- **engineering inference**;
- **known limitation or disagreement**.

No doctrine is used without its jurisdiction. Where public law, corporate law and technical access
control use the same word differently, the differences are retained.

## 2. Survey inputs

| ID | Commissioned survey | Principal use in INT-R5 | Material limitation |
| --- | --- | --- | --- |
| `S1` | *How authority is delegated, bounded, inherited and taken back* | delegation scope, amount, acting/succession, subdelegation, emergency, expiry, revocation and cure | comparative sample; consequences are regime-specific |
| `S2` | *What makes a body's decision the body's, and when it is a nullity* | forum, composition, quorum timeline, vote, decision mode, co-signature and proof record | no universal quorum, presence, meeting or nullity rule |
| `S3` | *Recusal, conflict of interest, and the prohibition on approving your own work* | structural self-approval, transaction-level SoD, COI taxonomy, recusal, waiver and detectability | many control sources are normative/audit practice rather than causal experiments |
| `S4` | *Authorization decided before the act, and what happens when it changes during* | authority-chain reduction, proof versus receipt, freshness horizon, checkpoint semantics and revocation | technical proof cannot decide jurisdiction-specific legal effect |
| `S5` | *Accepting another body's authority, and telling consultation from decision* | narrow recognition, retained local duties, act-effect taxonomy and responsibility allocation | recognition regimes transfer different assertions and remedies |

## 3. Delegation, appointment, amount and revocation

### 3.1 Transferable rule: one role edge is insufficient

**Classification: comparative legal synthesis plus engineering normalization.**

The delegation survey's central result is that `person → role → delegation` cannot establish the
right to decide. The effective authority depends on the source power, precise function, exclusions,
time, trigger, amount and valuation basis, geography, office status, subdelegation permission,
succession and exceptional conditions.

Primary anchors carried by the survey include:

- Commonwealth Australia, Acts Interpretation Act 1901, especially §§33A and 34AA–34AB;
- United States Federal Vacancies Reform Act, 5 U.S.C. §§3345–3349d;
- FAR 1.602-3 on unauthorized commitments and ratification;
- United Kingdom *Carltona* practice and *R v Adams*;
- public financial-delegation schemes using total transaction value and anti-splitting rules;
- UK Civil Contingencies Act 2004 for conditional emergency authority.

The target graph therefore distinguishes at least these edge kinds:

```text
DELEGATION
SUBDELEGATION
ACTING_APPOINTMENT
STATUTORY_SUCCESSION
IMPLIED_DEPARTMENTAL_AUTHORIZATION
AGENCY_AUTHORIZATION
EMERGENCY_AUTHORITY
RATIFICATION_OR_CURE
```

Collapsing them into `AUTHORIZED_BY` is rejected because their creation, scope, expiry and remedies
differ.

### 3.2 Monotonic attenuation

**Classification: formalized engineering rule supported by public-law and capability examples.**

For every child path:

```text
effective_scope(child) =
    effective_scope(parent)
    ∩ source_law_delegable_scope
    ∩ instrument_scope
    ∩ child_eligibility
    ∩ temporal_scope
    ∩ monetary_scope
    ∩ geographic_scope
```

The parent must also have possessed the power to subdelegate this power **when the child instrument
was created**. A presently valid parent cannot cure an invalid creation-time link by implication.

The closest technical analogue is SPKI/SDSI authorization reduction and attenuating capability
caveats. Neither supplies the legal source or issuer competence by itself.

### 3.3 Amount is a rule, not only a number

**Classification: recurring institutional-control pattern.**

A machine-readable amount boundary requires:

- limit;
- currency;
- valuation basis;
- aggregation window;
- related-transaction and anti-splitting rule;
- variation/options treatment;
- tax treatment;
- budget or cost-centre scope.

Checking the current invoice against a role limit is rejected. The comparison must be against the
economic transaction as defined by the applicable delegation scheme.

### 3.4 Acting and succession are independent provenance paths

**Classification: named legal rules; no universal default.**

Australian §33A can confer the powers of the office while a person lawfully acts and contains a
specific saving rule. The US FVRA instead makes eligibility, vacancy trigger, time, nomination status
and exclusive functions decisive. The DHS succession failure documented by GAO demonstrates why a
person's displayed title cannot be trusted without validating the path that placed that person in
office.

The graph must therefore keep the vacancy/trigger, succession rule, appointment event,
qualifications, start/end events and any saving provision separate from an ordinary delegation.

### 3.5 Post-hoc authorization is not one rule

**Classification: preserved legal disagreement.**

The target pre-action certificate always refuses when authority did not pre-exist the decision. A
later cure is a **new event and new legal question**. It never backdates the original certificate.

The surveyed regimes disagree:

- FAR 1.602-3 permits narrowly conditioned ratification of certain unauthorized commitments;
- the FVRA makes a defined class of actions “no force or effect” and non-ratifiable;
- corporate statutes such as DGCL §§204–205 create special validation procedures;
- other regimes use saving provisions, voidability or evidentiary presumptions.

Accordingly, `post_hoc_authorization` is a red fixture for the original pre-action claim while a
separate jurisdiction profile may later classify a cure as permitted, forbidden or unresolved.

## 4. Collegial validity

### 4.1 The act belongs to a legal organ, not a collection of people

**Classification: comparative legal rule.**

The collegial survey's transferable proposition is:

```text
competent organ
∩ lawful decision mode/forum
∩ valid composition
∩ applicable notice/agenda conditions
∩ quorum at the legally required time
∩ required vote
∩ constitutive form or co-signature, when applicable
```

This is a validation model, not one trans-jurisdictional substantive rule.

Primary anchors include DGCL §141 and *Fogel v. U.S. Energy Systems*; UK Model Articles 8–14;
German AktG §§107–108 and §124; US House quorum/voting procedure; and the California Brown Act.

### 4.2 Jurisdiction labels are mandatory

The words `quorum`, `present`, `meeting`, `majority`, `notice`, `agenda` and `consent` are not safe
standalone vocabulary. They require at least:

```text
jurisdiction
body_type
governing_instrument
decision_type
effective_date
rule_version
```

Examples preserved from the survey:

- Delaware normally computes board quorum from the authorized board and treats certain synchronous
  communications as presence;
- UK Model Articles ask whether directors can communicate information and opinions and require
  quorum when a proposal is put;
- a bespoke UK constitution may require specified categories throughout the meeting;
- German supervisory-board rules admit written votes and use their own decision-participation test;
- the US House uses a procedural presumption of continuing quorum until the rules trigger a count.

A universal `member_left => all later acts void` rule would therefore be false.

### 4.3 Event-sourced quorum proof

**Classification: engineering inference from the legal variation.**

A meeting-level Boolean is insufficient. The graph needs an event sequence such as:

```text
join
eligibility established
item opens
conflict declared
recusal begins
leave or disconnect
return
vote opens
vote cast
vote closes
```

Every decision item receives its own eligible roster, quorum denominator, participation test and
vote calculation under the applicable rule profile.

### 4.4 Co-signature is not quorum

Constitutional counter-signature, corporate joint representation, a second approval and a second
vote can all involve two persons while proving different propositions. The graph therefore models
co-signature/external execution as a separate predicate and never infers internal collegial validity
from the number of signatures on the resulting document.

### 4.5 Validity and provability are separate

Minutes can be constitutive, evidentiary or merely required records depending on the regime. German
AktG §107(2), UK Companies Act minutes provisions, *Fogel* and *Morris v Kanssen* collectively reject
`minutes signed => event true`. The certificate recomputes from underlying appointment, notice,
participation and vote evidence and records what evidentiary presumption, if any, the jurisdiction
profile permits.

## 5. Separation of duties, recusal and conflict

### 5.1 Self-approval is structural

**Classification: control invariant supported by access-control, audit-independence and judicial
examples.**

The COI survey distinguishes:

- **structural role incompatibility**, where one controlling subject closes both sides of a control;
- **conflict of interest**, which can be mandatory, manageable, waivable or disputed under the
  applicable regime.

`self_approval` belongs to the first class. Disclosure cannot make it valid.

Core candidate invariants are:

```text
Proposer(decision) ∩ Approver(decision) = ∅
Executor(effect) ∩ IndependentReviewer(effect) = ∅
MaterialContributor(work) ∩ IndependentReviewer(work) = ∅
```

For profiles that require it:

```text
Approver(effect) ∩ Executor(effect) = ∅
```

The identity compared is the real controlling subject, not username or account. Impersonation,
shared credentials or two accounts of one person do not create independence.

### 5.2 Meta-self-approval

A conflicted subject cannot be the sole decider of the exception:

```text
SubjectOfConflict(conflict) != SoleDeciderOfException(conflict)
```

Where real law leaves the initial recusal question to the potentially affected person, the graph
must record that adjudicator rule and cannot relabel the result “independently determined.”

### 5.3 Detectability boundary

**Classification: information boundary.**

Conflict facts are partitioned into:

1. **record-established** — exact self-approval, authorship, prior workflow role, toxic entitlements;
2. **record-indicated** — ownership, employer or relationship data that flags but does not fully
   settle the conflict;
3. **self-known/off-system** — friendship, promise, hostility, future employment or undocumented
   participation unavailable to the system;
4. **evaluative appearance** — external-observer tests requiring a competent human/legal judgment.

The certificate must not state “no conflict exists.” Its strongest automated statement is bounded:

> No prohibited role overlap or registered conflict was found in the named reconciled records;
> required current declarations were received; undisclosed/off-system facts are not disproved.

A regime that requires stronger resolution returns `not_established` until a competent producer
supplies it.

## 6. Pre-action proof, freshness and revocation

### 6.1 Authority at check is not authority at use

**Classification: information limit.**

A certificate produced at `t_check` proves only the result relative to the state it used. It cannot
contain a future revocation event. A system must therefore declare one of three semantics:

- snapshot/grandfathering;
- an issuer-authorized lease;
- revalidation before the next material or irreversible effect.

INT-R5 adopts `revalidation_before_commit` as the safe default for revocable authority. Snapshot or
lease behavior is available only when a jurisdiction/instrument profile expressly supplies it.

### 6.2 Proof, not receipt

A decision receipt says that one runtime returned `permit`. An authority proof supplies the chain,
policy, state, provenance and status evidence from which an independent verifier can recompute the
result. INT-R5 requires the second form.

Formal and technical anchors transferred by the survey include:

- SPKI/SDSI RFC 2693 authorization intersection, threshold subjects and result certificate;
- PKIX RFC 5280 path validation;
- RFC 5755 Attribute Certificates;
- XACML Administration and Delegation Profile;
- RBAC static/dynamic SoD;
- Rego/OPA, Cedar and Zanzibar-style relationship authorization;
- revocation/status examples from RFC 6960, RFC 7009, RFC 7662 and RFC 8693;
- NIST Zero Trust and continuous-access event patterns.

The languages can express predicates only when operands are supplied. Expressibility does not prove
the issuer, provenance or freshness of `recused=false`, `member=true` or `amount=...`.

### 6.3 Freshness horizon

The certificate carries a calculated evidence horizon:

```text
fresh_until = min(
    authority_path_expiry,
    status_next_update,
    appointment_or_attribute_expiry,
    policy_lease_expiry,
    state_attestation_expiry,
    operation_deadline
)
```

This is not a promise that no emergency revocation will occur before that time. It is the latest time
for which the admitted evidence remains within its declared freshness bounds.

### 6.4 Mid-operation revocation

The graph records at least:

```text
revocation_created_at
revocation_legally_effective_at
revocation_observed_at
```

Legal currentness follows the applicable effective-time rule. Before every protected irreversible
effect, the consumer re-resolves every revocable ancestor and decisive state assertion. A revocation
before the effect refuses or aborts it. A revocation after an irreversible effect cannot be disguised
as rollback; it stops downstream effects and opens the applicable incident, invalidation,
reissue/withdrawal and external-remedy path.

## 7. Cross-agency acceptance and act effect

### 7.1 Recognition is purpose-limited reliance

**Classification: comparative legal and federation-governance synthesis.**

Cross-agency acceptance is not `trusted_authority=true`. It is acceptance of a specific assertion,
from a specific source, under a specific legal gateway, for a specific purpose and scope, subject to
current status, authenticity, assurance/equivalence, refusal grounds and retained local duties.

Primary anchors include the HCCH 2019 Judgments Convention, eIDAS trusted-list and assurance
machinery, NIST SP 800-63C federation agreements, EU professional-qualification recognition,
*Aranyosi*, *Schrems II* and UK distinctions between agency agreements and non-binding MoUs.

The graph therefore stores:

```text
recognised_as
not_recognised_as
legal_basis
purpose
audience
scope
current_status
refusal_grounds
retained_local_duties
source_responsibility
acceptance_responsibility
final_decision_responsibility
execution_responsibility
```

Authentication of origin does not establish truth, institutional competence or authorization to
act.

### 7.2 Consultation, recommendation, approval and decision

**Classification: jurisdiction-profiled act-effect taxonomy.**

The classifier follows legal effect, not document title or UI verb. It records:

- formal source type;
- whether the act itself has binding effect;
- whether it is a condition precedent;
- whether the recipient is legally free to depart;
- whether departure requires reasons or permission;
- whether rights, obligations or legal position change;
- the legally operative document and ultimate decision-maker;
- reviewability and the competent review forum;
- practical departure cost as a diagnostic, never as a substitute for legal effect.

The survey's principal contrasts are:

- UK consultation is input while a proposal remains formative, not the final choice;
- TFEU Article 288 recommendations/opinions are non-binding, though they may be legally relevant;
- in the Banco Popular structure, Commission endorsement was the condition creating final binding
  effect and responsibility;
- under the US APA, a nominally advisory act can be final agency action where the process is complete
  and legal consequences follow, as illustrated by *Bennett v. Spear*.

## 8. Preserved disagreements and thin areas

The following are deliberately **not** normalized:

- consequences such as void, voidable, saved, curable, non-binding or non-ratifiable;
- when quorum must exist and how presence is established;
- whether a title defect invalidates an act or activates a saving rule;
- whether a conflict is non-waivable, waivable after disclosure or manageable;
- whether emergency authority is automatic, instrument-based or evaluative;
- whether a revocation affects an already-started operation;
- what recognition permits the accepting body not to re-examine;
- whether an approval is preparatory or itself the final binding decision.

Thin areas retained as uncertainty:

- no universal public-law notice grace period for revocation was established;
- some forum, recusal and emergency questions require evaluative legal judgment;
- the surveys do not establish a causal equivalence between compensating controls and true SoD;
- no system can prove the absence of facts known only to a person;
- technical standards provide proof containers and reduction mechanisms, not universal legal
  authority semantics.

## 9. Transfer verdict

The surveys support a narrow-scope design: a jurisdiction-profiled authority graph, monotonic chain
reduction, event-sourced collegial proof, transaction-level separation, bounded COI claims,
purpose-limited recognition, exact act-effect classification and revalidation before irreversible
effect.

They do **not** support one global authority Boolean, one universal nullity doctrine, a caller-supplied
certificate, or a claim that the repository already possesses this capability.
