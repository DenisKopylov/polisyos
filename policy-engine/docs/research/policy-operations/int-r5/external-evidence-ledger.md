# INT-R5 External Evidence Ledger — Amended

## 1. Status, source custody and use restriction

This ledger transfers findings from five commissioned surveys into INT-R5. The surveys are external
practice evidence. They are not repository capability, legal advice, registered PolicyOS vocabulary,
institutional appointments or authority to implement.

Exact source identities, SHA-256 digests, line/byte denominators, claim anchors and branch-local
admitted evidence extracts are in [`survey-source-manifest.md`](survey-source-manifest.md). The full
survey bytes remain external artifacts. Therefore the branch can replay each transferred claim against
the admitted extracts and source identity, while full-byte re-verification requires the external file
matching the manifest digest. No section below claims more.

Transferred statements are classified as:

- named legal rule in a named jurisdiction/regime;
- formal or technical mechanism;
- control/design pattern;
- empirical finding;
- engineering inference;
- known limitation or disagreement.

No doctrine is used without jurisdiction. Public law, corporate governance and technical access
control may use the same word differently; those differences are preserved.

## 2. Survey inputs and exact package anchors

| ID | Exact commissioned survey | Package anchors | Principal use | Limitation |
|---|---|---|---|---|
| `S1` | *Глубокое исследование: как полномочие делегируется, ограничивается, наследуется и отзывается* | `S1:5-9`, `102-130`, `162-272`, `298-381` | delegation scope, amount, succession, subdelegation, emergency, revocation and cure | comparative regimes; consequences differ |
| `S2` | *Когда решение принадлежит коллегиальному органу — и когда оно юридически не существует* | `S2:5-13`, `28-90`, `120-166` | forum, composition, quorum, vote, mode, co-signature and proof | no universal quorum/presence/nullity rule |
| `S3` | *Рекузал, конфликт интересов и запрет самосогласования: как не дать участнику замкнуть контур контроля на себе* | `S3:3-80`, `136-178` | structural self-approval, SoD, COI, recusal and detectability | many sources are control/audit standards, not causal trials |
| `S4` | *Предварительная авторизация как проверяемое доказательство: цепочки полномочий, свежесть и отзыв в ходе действия* | `S4:5-29`, `82-173`, `189-375`, `377-550` | proof versus receipt, chain reduction, freshness and revocation | technical proof cannot determine jurisdiction-specific legal effect |
| `S5` | *Принятие полномочий другого органа: когда доверие защищаемо и где проходит граница между консультацией, рекомендацией, одобрением и решением* | `S5:3-68`, `70-170`, `172-236` | purpose-limited recognition, act effect and responsibility | regimes transfer different assertions and remedies |

## 3. Delegation, appointment, amount and cure

### 3.1 One role edge is insufficient

**Classification:** comparative legal synthesis plus engineering normalization.  
**Anchor:** `S1:5-9`, `S1:19-43`.

`person → role → delegation` cannot prove the right to decide. Effective authority depends on source
power, exact function and exclusions, time and triggers, amount/valuation, geography/place, office
status, subdelegation permission, succession and exceptional conditions.

The target graph therefore keeps separate edges for delegation, subdelegation, succession/acting,
implied departmental authorization, agency authorization, emergency authority and cure/validation.
Collapsing them into one `AUTHORIZED_BY` edge is rejected.

### 3.2 Monotonic attenuation and creation-time power

**Classification:** conservative reducer invariant supported by named public-law and capability
examples.  
**Anchor:** `S1:162-192`.

```text
effective_scope(child) :=
    effective_scope(parent)
    ∩ source_law_delegable_scope
    ∩ instrument_scope
    ∩ child_eligibility
    ∩ temporal_scope
    ∩ monetary_scope
    ∩ geographic_scope
```

The parent must also have possessed the right to create the child link at creation time. This is not
promoted into one universal legal doctrine; a jurisdiction profile still determines the legal source
and exceptions.

### 3.3 Amount is a valuation rule

**Classification:** recurring institutional-control pattern.  
**Anchor:** `S1:102-130`.

A machine-readable boundary requires limit, currency, valuation basis, aggregation window,
related-transaction/anti-splitting rule, variation/options and tax treatment, and budget scope. The
comparison is against the economic transaction defined by the applicable scheme, not one submitted
invoice.

### 3.4 Acting, succession and emergency are independent paths

**Classification:** named legal rules and control mechanisms; no universal default.  
**Anchor:** `S1:194-272`.

Australian §33A, the US FVRA, UK Carltona practice and emergency regimes use different sources,
activation facts, scopes and consequences. A displayed title or generic emergency flag is not enough.
The graph keeps vacancy/trigger, succession/designation rule, qualifications, start/end events,
saving provisions and emergency predicates distinct.

### 3.5 Post-hoc cure and temporal legal effect

**Classification:** preserved legal disagreement.  
**Anchor:** `S1:328-381`.

The original pre-action question remains: did authority pre-exist the original decision? Later
evidence cannot be inserted into that historical snapshot. A later cure is a new event/result.

Surveyed outcomes include:

- conditioned ratification under FAR;
- relation back that can fail because an original filing window or right has intervened, as in the
  FEC v NRA analysis;
- express non-ratifiability under the defined FVRA rule;
- other validation/cure outcomes;
- statutory saving, which is not ratification.

The amended model therefore requires:

```text
prospective | relation_back | saved_act | limited | unresolved
```

with `legally_effective_from` and `historical_certificate_mutated: false`. No universal denial or
universal permission of relation back is adopted.

## 4. Collegial validity

### 4.1 The act belongs to a legal organ

**Classification:** comparative legal validation model.  
**Anchor:** `S2:5-13`, `S2:28-54`.

A document, signatures or minutes do not alone prove that the competent legal organ acted. The model
checks organ competence, permitted forum/mode, composition, notice/agenda where applicable, quorum at
the required time, vote and any constitutive form/co-signature.

The consequence of a defect remains profile-specific: no act/invalid, voidable/challengeable,
curable, saved, evidentiary-only or execution/authentication defect are not normalized into one
universal Boolean.

### 4.2 Forum and membership are distinct

**Classification:** named comparative rule plus engineering predicate.  
**Anchor:** `S2:50-54`, `S2:97-103`.

Correct people sitting as a committee do not become the full board for a reserved matter. The target
predicate is `actual_forum == competent_forum_for(matter)`, not membership inclusion.

### 4.3 Quorum is event- and profile-relative

**Classification:** engineering inference from legal variation.  
**Anchor:** `S2:57-90`, `S2:120-155`.

The same leave/recusal event can have different consequences under `at_vote`,
`throughout_meeting` and `presumptive_until_challenged` profiles. The model therefore stores a
participation timeline and recomputes each decision item. Presence, abstention and affirmative vote
remain distinct. Remote participation is evaluated under the named legal test.

### 4.4 Co-signature is not quorum

**Classification:** comparative structural distinction.  
**Anchor:** `S2:149-159`.

Counter-signature, joint external representation, a second approval and a second vote may each involve
two persons while proving different propositions. Signature count cannot imply internal collegial
validity.

## 5. Separation of duties, recusal and detectability

### 5.1 Structural self-approval

**Classification:** control invariant supported by access-control, audit-independence and judicial
analogies.  
**Anchor:** `S3:3-49`, `S3:136-178`.

A controlling subject cannot close incompatible roles on the same transaction. Disclosure cannot
cure configured structural self-approval. Identity comparison resolves alternate accounts,
impersonation and delegated-user sessions rather than comparing usernames.

A conflicted subject cannot be the sole producer of their exception. Additional incompatible role
pairs remain profile/risk specific rather than universalized.

### 5.2 Detectability boundary

**Classification:** information boundary.  
**Anchor:** `S3:51-80`.

Conflict evidence is partitioned into record-established, record-indicated, self-known/off-system and
evaluative appearance classes. The certificate never states “no conflict exists.” Its strongest
automated statement is bounded to named reconciled records and current declarations, and it states
that undisclosed/off-system facts are not disproved.

Where a profile requires stronger adjudication and no competent adjudicator exists, the result is
`not_established`.

## 6. Pre-action proof, non-inferability and freshness

### 6.1 Corrected information-limit transfer

**Classification:** formal/technical information limit.  
**Anchor:** `S4:5-29`.

The survey's prose establishes that a `t0` certificate cannot contain a future `t1` revocation event
and therefore cannot determine all later histories. The amended package does **not** transfer the
survey's illustrative `authority at check != authority at use` as a universal equation.

The admitted proposition is:

```text
there exist two histories identical through t0
whose authority at t1 differs
```

An unchanged history is allowed. The architecture still requires explicit snapshot, issuer-authorized
lease or revalidation/checkpoint semantics.

### 6.2 Proof, not receipt

**Classification:** technical/formal mechanism.  
**Anchor:** `S4:82-173`.

A decision receipt says one runtime returned permit. An authority proof carries enough chain, policy,
state, provenance, status and commitment evidence for independent recomputation. Exact action,
principal/audience, scope, time, policy, external-state evidence, quorum branches and temporal mode
remain separate coordinates.

### 6.3 Predicate expressibility is not operand provenance

**Classification:** engineering limitation.  
**Anchor:** `S4:35-80`, `S4:189-375`.

RBAC/ABAC/XACML/Rego/Cedar/Zanzibar/capabilities/SPKI can express useful parts of the problem, but a
language accepting `recused=false`, `decision_time=x` or `amount=y` does not prove who produced those
operands or whether they are fresh. This supports the amended independent-producer table and the rule
that canonicalization establishes bytes, not semantic truth.

### 6.4 Freshness and mid-operation revocation

**Classification:** control and distributed-systems synthesis.  
**Anchor:** `S4:377-550` and later operation-semantics sections.

Freshness is bounded by evidence expiry/status propagation and checkpoints. A result records
`fresh_until` but does not promise that emergency revocation cannot occur sooner. Snapshot, lease and
checkpoint semantics allocate risk differently. Before an irreversible effect the applicable
currentness predicate is re-evaluated; after an irreversible effect the system preserves history and
routes consequence rather than claiming fictional rollback.

## 7. Cross-agency acceptance and act effect

### 7.1 Purpose-limited recognition

**Classification:** comparative legal and federation-governance synthesis.  
**Anchor:** `S5:3-68`, `S5:70-123`.

Cross-agency acceptance is reliance on one assertion from one source, for one purpose/scope, under a
legal/trust gateway, subject to status, authenticity/assurance, refusal grounds, retained duties and
responsibility allocation. It is not blanket trust or transfer of all competence.

The graph stores `recognised_as` and `not_recognised_as`. Authentication of origin does not establish
truth; identity/assurance does not establish substantive authorization; recognition does not erase the
accepting body's own duties.

### 7.2 Consultation, recommendation, approval and decision

**Classification:** jurisdiction-profiled act-effect taxonomy.  
**Anchor:** `S5:125-170`, `S5:172-236`.

Classification follows legal effect and responsibility, not document/UI title. It records formal
source type, binding effect, condition precedent, legal freedom to depart, reasons requirement,
operative act, ultimate maker, reviewability and practical departure cost. Formal bindingness and
practical pressure remain distinct axes.

## 8. Preserved disagreements and thin areas

The package does not normalize:

- void, voidable, saved, curable, non-binding and non-ratifiable consequences;
- quorum denominator, temporal persistence, remote presence or alternative decision mode;
- title defects and saving provisions;
- mandatory, manageable or waivable conflicts;
- emergency source/necessity determinations;
- operation treatment after revocation;
- what a recognition regime permits the acceptor not to re-examine;
- whether an approval is preparatory or the final binding decision;
- prospective versus relation-back cure effect.

No universal public-law notice grace period was established. Some forum, apparent-bias, recusal,
emergency and cure questions require a competent human/legal adjudicator. Technical proof containers
do not create legal competence.

## 9. Transfer verdict and residual

The five surveys support a jurisdiction-profiled authority graph, monotonic reduction, event-sourced
collegial proof, transaction-level separation, bounded conflict claims, purpose-limited recognition,
explicit act effect and dependency-aware freshness.

They do not support one global authority Boolean, one nullity doctrine, a caller-produced positive, a
universal cure rule or a claim that the repository already implements the capability.

Branch-local claim replay is supported by `survey-source-manifest.md`. Full original-survey byte
reverification remains dependent on the external artifacts matching the recorded digests. This
residual is explicit; the package does not describe it as closed by prose alone.
