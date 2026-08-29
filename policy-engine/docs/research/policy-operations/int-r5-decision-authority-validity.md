---
title: "INT-R5 — Pre-action decision authority proof"
research_id: INT-R5
status: delivered_research
kind: deep-research
result_type: accepted_narrow_scope
research_only: true
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r5-research
current_repo_baseline: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
inspection_date: 2026-08-29
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
repository_verdict: shipped_model_sound_but_materially_incomplete
canonical_owner_files_inspected: 10
external_surveys_consumed: 5
authoritative_for:
  - research-level specification of a DecisionAuthorityGraph
  - research-level specification of a pre-action DelegationValidityCertificate
  - bounded comparison of that specification with the pinned shipped repository
  - red-first semantic fixtures for later implementation
  - implementation-routing and kill criteria for this authority capability
may_not_use_for:
  - production implementation authorization
  - final wire, schema, database, package, API, or serialization contract
  - legal-sufficiency conclusion in any jurisdiction
  - institutional appointment or authority grant
  - capability claim
  - permission to publish, approve, execute, or open a gate
  - individual-case authorization governed by PAO-R4
supporting_files:
  - int-r5/repository-baseline.md
  - int-r5/external-evidence-ledger.md
  - int-r5/decision-authority-specification.md
  - int-r5/adversarial-fixtures.md
---

# INT-R5 — Decision Authority Graph And Delegation Validity Certificate

## 1. Task And Project Fit

### 1.1 Exact question

How can PolicyOS establish, **before a protected effect**, that one identified person or one
identified collegial body had the right to make **this exact decision** in the relevant role,
jurisdiction, subject matter, amount band, time window, forum, quorum, co-signature and
conflict-of-interest posture?

The research result is a `DecisionAuthorityGraph` and a
`DelegationValidityCertificate`. The graph preserves authority provenance and
jurisdiction-dependent predicates. The certificate is a reproducible pre-action reduction of that
graph against an exact decision commitment and evaluation time. It is not an approval asserted by
the requester and not an audit trail assembled after execution.

### 1.2 Why this remained research-first after the sequencing failure

The backlog ordered `INT-R5` before `GY-PA2`, Atlas `DS9` and `DS14`, the DS20 vocabulary and
acquisition approvals. At the pinned baseline, `GY-PA2`, `DS9` and `DS20` have shipped and the
acquisition-approval path composes their primitives. The sequencing failure does not convert shipped
behavior into the correct model. This pass therefore kept two objects separate:

1. **Requirement-derived model** — derived from the question, identity decision and five external
   surveys without accepting shipped fields merely because they exist.
2. **Repository comparison** — mapping shipped predicates to that model, including explicit
   absences and contradictions.

The early-stop condition was a materially wrong merged authority rule requiring an architect ruling.
No such contradiction was found. The shipped controls are sound inside their declared operational
boundaries and materially incomplete as proof of institutional decision authority.

### 1.3 False production claims prevented

This result rejects the following equivalences:

- verified login, runtime role and permission **do not equal** institutional competence;
- fresh MFA or step-up **does not equal** a valid delegation or appointment;
- a signed `HumanDecisionRecord` **does not prove** that a collegial body validly acted;
- a `governance_board` role token **does not prove** forum, composition, quorum or voting;
- a disclosed conflict **does not cure** structural self-approval;
- a permit computed at `t_check` **does not prove** authority at a later irreversible effect;
- an authenticated external assertion **does not equal** cross-agency legal recognition;
- a UI action called `approve` **does not determine** whether the legal act was consultation,
  recommendation, condition-precedent approval or a binding decision.

The most dangerous false claim would be: “DS20 admitted the request and DS9 persisted a signed human
decision, therefore the named person or body was legally entitled to decide.” The repository does
not support that conclusion.

### 1.4 Four-way boundary verdict

| Plane | Verdict | PolicyOS responsibility | Boundary retained |
| --- | --- | --- | --- |
| Computation and custody of PolicyOS's own authority-validity statement | **OWN** | Recompute, bind, persist, monitor and replay the certificate or typed refusal. | PolicyOS owns its statement, not the office, meeting or external power. |
| Appointments, delegations, meeting/quorum records, conflict/recusal decisions, recognition and legal-effect rules | **INTEGRATE** | Define typed purpose-limited interfaces; verify issuer, signature, scope, applicability and currentness. | External institutions remain source and adjudicator. |
| Institutional succession and changes in who answers for external authority | **OBSERVE** | Consume changes because they can freeze or invalidate PolicyOS's certificate. | PolicyOS does not run succession or appoint holders. |
| Meetings, appointments, disputed recusal adjudication, legal effect, execution and remedies | **OUT_OF_SCOPE** | Name the external owner and refuse when evidence is absent. | No administrator, court, case manager or executor role is absorbed. |

This extends the identity decision's existing §6 pattern: PolicyOS owns the contract and reaction of
its signature while integrating or observing the sovereign function.

### 1.5 PAO-R4 boundary

`PAO-R4` remains the individual-use firewall. `INT-R5` answers **who or which body had authority to
make a decision**. It does not establish individual facts, decide whether a policy-level artifact
may be applied to an individual, or authorize an individual outcome. A valid
`DelegationValidityCertificate` cannot substitute for `PAO-R4`, and a `PAO-R4` pass cannot establish
the decision-maker's competence.

### 1.6 Result in one sentence

**The shipped model is sound but materially incomplete: it can prove a verified runtime principal
had a current resource-bound permission and bounded human-decision mandate for a protected
operation, but it cannot prove the full institutional proposition that the person or body had
authority to make this exact decision.**

## 2. Current Repo Baseline

### 2.1 Pin, holder and denominator

- Repository: `DenisKopylov/polisyos`
- Pinned baseline: `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`
- Research branch: `research/int-r5-research`
- Step-0 skeleton commit: `000573d25bf3f38bdd8042e59f5ab4a1e59ab0c1`
- Measurement holder: this INT-R5 pass through exact authenticated GitHub reads.
- Canonical executable denominator: **10 files — nine Python owners and one Rego mirror**.
- GitHub search-index zeroes were orientation only; executable absence claims come from reading the
  complete named owner closure.

The full coordinate ledger is
[`int-r5/repository-baseline.md`](int-r5/repository-baseline.md).

### 2.2 Shipped component verdicts

| Component | What it actually proves | Verdict |
| --- | --- | --- |
| `GY-PA2` | Five operational predicates — verified identity, explicit permission, mandate-bounded delegation, operation in envelope and live accountability — with exact operation/resource/subject/tenant/time/status binding. | **Sound but incomplete.** No source-law/jurisdiction, amount, parent grant, succession, collegial validity, COI, recognition or legal-effect model. |
| `DS9` | Issuer-qualified human actor, separation from custody signer, exact evidence/presentation binding, narrow reviewer separation, strict source union, currentness re-resolution, CAS/event/idempotent guarded persistence. | **Sound but incomplete.** No general proposer/approver/executor/reviewer lineage, quorum, recusal, amount, succession or recognition. |
| `DS20` | Verified runtime principal, exact permission, operation, resource binding, authorization source and signed replay-protected step-up; Python/Rego permission parity. | **Sound within boundary.** It proves runtime authorization, not institutional competence. |
| acquisition-approval composition | `EVIDENCE_ACQUIRE` + request-bound acquisition resource + `ACQUISITION_APPROVAL` step-up, with PA2/DS9 mandate/currentness and guarded use. | **Sound but incomplete.** Closest pre-effect seam, still no institutional certificate. |

Historical DS20 closure recorded 29 unsafe POST operations and 29/29 admission/denial witnesses. At
the pinned post-DS9 baseline, Python and Rego each contain **34** exact permissions. The older prose
count of 33 is documentation drift caused by the later `runs.human_decisions.create` addition, not a
parity failure.

### 2.3 Attribute-by-attribute repository capability

`represented` means the current chain carries and enforces the required semantic. `partial` means a
narrower predicate exists. `not representable` means the strict owner closure has no field, producer
and consumer for the semantic.

| Required attribute | Today | Positive coordinate | Missing part |
| --- | --- | --- | --- |
| Temporal and subject-matter delegation | **partial** | `DelegatedActionEnvelope`; PA2 currentness | source law/jurisdiction, amount/valuation, reserved matters and full legal-purpose scope |
| Quorum and co-signature | **not representable** | board role label only | body/forum, roster, timeline, denominator, vote branches, quorum profile and co-signature purpose |
| Separation of duties | **partial** | DS9 `ReviewerSeparationCredential` | complete transaction lineage and controlling-subject resolution |
| Recusal and conflict of interest | **not representable** | none | disclosure, detected conflict, recusal, waiver/management and detectability boundary |
| Acting appointments and succession | **not representable** | current principal/role only | office, vacancy, acting basis, succession order, qualifications and predecessor path |
| Subdelegation limits | **not representable** | none | parent grant, right/depth, delegee class, attenuation and creation-time power |
| Expiry and emergency authority | **partial** | envelope validity/status | emergency source, trigger, necessity/urgency, exceptional scope and expiry profile |
| Revocation mid-operation | **partial** | re-resolution before DS9 protected use | checkpoint/cancel/irreversible-effect and post-effect consequence semantics |
| Cross-agency acceptance | **not representable** | producer authentication only | legal gateway, accepted assertion type, negative perimeter, refusal grounds and retained duties |
| Consultation/recommendation/approval/binding decision | **not representable** | workflow verbs only | legal effect, condition precedent, freedom to depart, operative act and ultimate maker |

Cross-cutting coordinates:

| Coordinate | Today |
| --- | --- |
| specific person and runtime role | represented |
| exact runtime operation and resource | represented |
| time window/currentness | represented narrowly |
| jurisdictional competence | not representable |
| amount threshold, currency, aggregation and valuation | not representable |
| conflict-of-interest posture | not representable |
| collegial-body validity | not representable |

### 2.4 Capability label and reuse-first path

The complete capability is **`absent/unallocated`**, not `contract_only`: there is no admitted
`DecisionAuthorityGraph`, no certificate, no appointed institutional producer, no complete bridge,
no enforcing consumer and no semantic e2e chain. This research does not change that label.

The smallest reuse path is to extend the existing mandate/delegation owner, consume the certificate
through DS9's pre-effect/currentness/guarded-store seam, retain DS20 as the narrow
operation/resource/permission floor, reuse CAS/signature/event/audit machinery, integrate external
institutional facts through typed adapters, project through Atlas/DS14, and keep `PAO-R4` separate.

## 3. External Research Baseline

### 3.1 Inputs and source discipline

Five commissioned surveys were consumed:

1. delegation scope, amount, expiry, acting/succession, subdelegation, emergency, revocation and
   cure;
2. collegial competence, forum, composition, quorum, vote, decision mode and co-signature;
3. structural self-approval, SoD, COI, recusal, waiver and detectability;
4. pre-action proof, chain reduction, freshness and mid-operation revocation;
5. cross-agency recognition and consultation/recommendation/approval/decision taxonomy.

The transfer ledger is
[`int-r5/external-evidence-ledger.md`](int-r5/external-evidence-ledger.md). It distinguishes named
legal regimes, formal mechanisms, control patterns, empirical findings, engineering inferences and
known limitations. External vocabulary is not silently registered as PolicyOS vocabulary.

### 3.2 High-confidence transferable results

- `person → role → delegation` is insufficient; the decision right is the intersection of source
  power, exact function, exclusions, time, trigger, amount/valuation, geography, appointment,
  subdelegation, succession, emergency and current status.
- A child path cannot amplify its parent, and the parent must have possessed the right to create the
  child link at creation time.
- Acting, statutory succession, implied departmental authorization, emergency authority and cure are
  distinct provenance edges, not aliases for delegation.
- The legal organ and forum matter independently of the people present. Membership equivalence is
  not organ equivalence.
- Quorum is item- and profile-relative. It requires an event timeline, valid authority branch per
  participant and the applicable denominator/temporal rule, not a count or opening Boolean.
- Co-signature is a separate layer from quorum and internal approval.
- Self-approval is a structural role incompatibility, not a disclosed COI that can be waived by the
  conflicted actor.
- No system can prove the absence of conflicts known only to a person; a positive statement must be
  bounded to named records and current declarations.
- A pre-action certificate proves a proposition relative to `t_check`; it cannot know a later
  revocation. Snapshot, lease or revalidation semantics must be explicit.
- A decision receipt is not an authority proof. The latter must carry the chain, policy, state,
  provenance, status and replay material needed for independent recomputation.
- Cross-agency acceptance is purpose-limited reliance on a specific assertion under a legal/trust
  gateway, with a positive scope and negative perimeter; it is not blanket trust.
- Act type follows legal effect and responsibility, not title or UI verb.

### 3.3 Preserved disagreements

The research does not create universal answers for:

- `void`, `voidable`, saved, curable, non-binding and non-ratifiable consequences;
- the denominator and temporal persistence of quorum;
- the legal meaning of remote presence and written votes;
- whether a title defect destroys or is saved for a particular act;
- which COI grounds are mandatory, manageable or waivable;
- whether authority is protected at start, leased or revocable at checkpoints;
- what a recognition regime permits the acceptor not to re-examine;
- whether an approval is preparatory or itself the final binding act.

Every such predicate therefore requires a versioned `jurisdiction + body_type + governing
instrument + decision_type + effective_date` profile. Unknown profile or unresolved evaluative
question cannot yield a positive.

### 3.4 External limitations

- The surveys support formal and control design more strongly than causal equivalence of compensating
  controls to true separation.
- Some forum, deception, apparent-bias and emergency-necessity questions require a competent human or
  legal adjudicator.
- Technical standards provide proof containers, path reduction, threshold and status mechanisms;
  they do not create universal legal competence.
- No universal public-law notice grace period for revocation was established.

## 4. Result

### 4.1 Result type

**`accepted_narrow_scope`.** The research supports a jurisdiction-profiled, pre-action authority
proof with exact decision/effect binding, graph reduction, event-sourced collegial evidence,
transaction-level separation, bounded conflict claims, purpose-limited recognition and mandatory
freshness semantics. It does not support a universal legal-validity Boolean or a production claim.

### 4.2 Information-limit theorem

For mutable authority state:

```text
authority_at_check(t0) != authority_at_use(t1)
```

unless the applicable regime explicitly selects snapshot/grandfathering, an issuer-authorized lease,
or revalidation/checkpoint semantics. A certificate at `t0` cannot contain a truthful event that
first occurs at `t1 > t0`. Therefore a pre-action positive must carry `as_of`, `fresh_until`, mutable
dependencies and the required pre-effect revalidation mode.

### 4.3 `DecisionAuthorityGraph`

The graph binds one canonical decision and protected effect. It contains typed nodes for source
power, jurisdiction profile, institution, office, principal, appointment, vacancy/trigger,
delegation, recognition rule/external act, forum/session/item/participation, conflict/recusal,
separation, amount valuation, emergency predicate, revocation/invalidation and act effect.

It preserves distinct edges for delegation, subdelegation, acting/succession, implied/agency
authorization, emergency, recognition, forum/quorum/vote/co-signature, transaction roles,
conflict/recusal, revocation, cure and the four act-effect relationships.

Every load-bearing statement carries issuer, producer, source class, jurisdiction/rule version,
validity/currentness, evidence refs, authority boundary and a P37 admission class. A fact whose
origin is `institutionally_supplied` becomes positive only after issuer/signature/content/scope/time
verification makes the gate predicate `recomputed` or `independently_reconciled`.

The full research sketch is
[`int-r5/decision-authority-specification.md`](int-r5/decision-authority-specification.md).

### 4.4 Path reduction

For each root-to-actor/body path:

```text
effective_scope    := intersection(root and every child scope)
effective_validity := intersection(root and every child validity interval)

for every link:
    verify issuer and signature
    verify prior subject/grantor continuity
    verify permission to delegate this power
    verify creation-time grantor power
    verify appointment/trigger/qualification/currentness
    verify mandatory constraints and status
    reject path on empty scope/validity or unknown critical rule
```

One invalid path does not destroy an independent path. A conjunction or threshold fails when the
remaining valid branches cannot satisfy its rule.

### 4.5 Ten required attributes in the target model

| Attribute | Target graph predicate |
| --- | --- |
| temporal and subject delegation | root/source-law path, effective-scope and validity intersection, reserved matters, amount/place/purpose |
| quorum and co-signature | competent forum, lawful composition, event-sourced participation, profile-specific threshold/vote, separate constitutive signature |
| separation of duties | controlling-subject lineage across proposer, contributor, approver, executor and independent reviewer |
| recusal and COI | registered/detected/declared facts, bounded detectability, competent recusal/waiver/management producer |
| acting and succession | vacancy/trigger, applicable succession/designation rule, qualifications, start/end and saving provisions |
| subdelegation | parent ref, right/depth/delegee class, creation-time power and monotonic attenuation |
| expiry and emergency | interval/event expiry plus named emergency source, trigger, scope, necessity/urgency and end condition |
| mid-operation revocation | dependency index, legal-effective time, pre-effect/checkpoint revalidation and honest post-effect consequence |
| cross-agency acceptance | legal gateway, source competence, assertion type/scope/status/assurance, refusal grounds, negative perimeter and retained duties |
| act-type distinction | formal type, binding effect, condition precedent, departure freedom, operative act, ultimate maker and reviewability |

### 4.6 `DelegationValidityCertificate`

The certificate is a local result union — `pre_action_valid | refused | not_established |
not_applicable` — that feeds the one Atlas/system lattice. It does not create a new global status
system.

It includes:

- certificate ID and technical custody proof;
- exact decision and effect commitments;
- principal/body, office/role and graph-root refs;
- `issued_at`, `as_of`, `fresh_until` and profile-selected revalidation mode;
- surviving authority paths and effective scope/validity;
- one receipt for every decisive predicate with producer, evidence, P37 class and freshness;
- every mutable dependency;
- stable local refusal reasons and limitations;
- `authoritative_for` this exact pre-action proposition;
- `may_not_use_for` any other decision/effect, legal-sufficiency claim or PAO-R4 individual use.

The requester cannot construct a positive certificate or select the least restrictive freshness
mode. The PolicyOS signature attests to the computation only.

### 4.7 Unappointed-holder behavior

A required role exists independently of its holder. With no qualifying appointment:

```yaml
local_result: not_established
refusal_codes: [MISSING_APPOINTED_HOLDER]
missing_role_or_owner_refs: [exact required role]
```

The output also names the appointing authority or marks it unestablished and states the evidence
needed. This is a normal result, not an exception. Candidate computation, demonstration, negative
replay and non-authority surfaces continue. Later appointment changes graph data; no model or schema
change is needed. A team name, maintainer, runtime role or adjacent signer may not be substituted.

### 4.8 Detectability boundary

The certificate separately reports:

1. record-established structural conflicts;
2. record-indicated conflicts requiring adjudication;
3. current participant declarations;
4. off-system/self-known conflicts whose absence is not provable;
5. evaluative apparent-bias questions and their competent adjudicator.

Its strongest automated COI statement is bounded to named reconciled records and declarations. A
profile requiring stronger resolution returns `not_established`; PolicyOS does not borrow an
adjudicator.

### 4.9 Freshness and revocation

`fresh_until` is the minimum of authority-path expiry, status next-update, appointment/attribute and
conflict-declaration expiry, recognition status, policy lease and effect deadline. It is an evidence
bound, not proof no emergency revocation can arrive sooner.

Default mode is `revalidate_before_commit` for revocable authority. Snapshot or lease behavior
requires an explicit profile and competent issuer. Before an irreversible effect, any legally
effective revocation refuses the effect. After an irreversible effect, PolicyOS preserves history,
stops dependent effects and routes invalidation/incident/reissue/withdrawal/remedy; it does not claim
an impossible rollback.

### 4.10 Explicit repository verdict

No merged component is wrong within its stated purpose. The failure is **coverage and sequencing**,
not an unsafe universal rule already embedded in production:

- `GY-PA2`: sound, incomplete;
- `DS9`: sound, incomplete;
- `DS20`: sound within runtime authorization, incomplete for institutional competence;
- acquisition gateway: sound composition, incomplete and the natural certificate landing seam.

No architect-stop finding fired.

## 5. Counterexamples And Failure Modes

The complete red-first definitions are in
[`int-r5/adversarial-fixtures.md`](int-r5/adversarial-fixtures.md).

| Required fixture | Unsafe conclusion | Required result |
| --- | --- | --- |
| `self_approval` | two accounts or disclosure create independence | refuse `SELF_APPROVAL` and `SEPARATION_OF_DUTIES_FAILED`; zero effect |
| `expired_delegation` | current permission/MFA revives expired grant | refuse `DELEGATION_EXPIRED`; no surviving path/effect |
| `wrong_forum` | correct people/signatures convert committee into full board | refuse `FORUM_NOT_COMPETENT`; quorum not used to rescue forum |
| `quorum_loss` | opening quorum remains true for every later item | recompute by profile and refuse `QUORUM_LOST_AT_DECISION` where applicable |
| `post_hoc_authorization` | later grant/ratification can backdate original validity | original certificate remains refused `AUTHORITY_NOT_PREEXISTING`; later cure is a new result |

Additional failure classes:

- current invoice checked instead of aggregate transaction;
- child grant wider than parent;
- displayed acting title with invalid succession root;
- requester-supplied emergency;
- one authenticated foreign assertion treated as local competence;
- recommendation auto-executed as binding decision;
- certificate reused for another recipient, amount or effect;
- conflict/status provider absent but absence treated as permission;
- late quorum/recusal/revocation event silently ignored;
- current law/state substituted into historical replay;
- chair/minutes conclusion accepted without underlying evidence;
- technical signer treated as institutional grantor.

## 6. Benchmark Or Fixture Proposal

### 6.1 Corpus

The future semantic suite has:

- a frozen public pack containing the five required fixtures, profile variants, valid near-pass
  controls, field mutations, unappointed-holder, negative-perimeter and title-versus-effect cases;
- a sealed holdout changing names, edge order, document titles, account aliases and harmless
  metadata and including structurally novel equivalents;
- explicit jurisdiction/rule-profile assumptions for every case;
- authority-admissibility labels, not claims of ultimate legal truth.

### 6.2 Metrics

```text
false_grant
false_refusal
wrong_refusal_reason
missed_dependency
stale_certificate_use
commitment_replay_or_substitution
profile_collapse
post_hoc_backdating
unbounded_conflict_claim
```

`false_grant` is primary. A test passing because no real producer or consumer exists is vacuous.

### 6.3 Required test shape

Each fixture must run through the real reducer, persistence/revalidation bridge and protected
consumer; assert exact effect count; read back the graph, certificate/refusal and dependency events;
run a near-pass and adversarial variants; prove no sibling consumer bypass; and verify the verifier
with corruption. Marker or reason-code presence is insufficient.

### 6.4 Fault injection

Required drills include provider loss before effect, delayed/out-of-order/duplicate revocation,
corrupted parent grant, removed quorum branch, late recusal changing denominator, conflicting
recognition status, guarded-store failure, historical profile change and mass root invalidation.
Recovery must fail closed, remain idempotent, preserve history and never execute without final
currentness.

## 7. Artifact Contract Sketch

### 7.1 Graph and certificate contracts

The detailed candidate node/edge vocabulary, common claim envelope, reducer, refusal vocabulary and
certificate fields are defined once in
[`int-r5/decision-authority-specification.md`](int-r5/decision-authority-specification.md).

Every decisive graph fact carries:

```text
claim identity and typed assertion
jurisdiction and governing rule version
named non-requester producer and issuer
P37 admission class
legal/observed/freshness times
evidence refs and content binding
authoritative_for / may_not_use_for
```

### 7.2 Producer rule

The requester may provide raw candidate material but cannot produce the canonical decision/effect
commitment, appointment, authority path, amount aggregate, quorum result, conflict determination,
recognition result, act effect or positive certificate. Each is recomputed or independently
reconciled by its owner.

### 7.3 One-lattice rule

`pre_action_valid`, `refused`, `not_established` and `not_applicable` are local certificate outcomes.
They are inputs to the existing status lattice. Atlas DS4 or its successor owns the projection
mapping. No `authority_status` lattice is created here.

### 7.4 Canonical owner map

| Concern | Existing owner/placement | Disposition |
| --- | --- | --- |
| operational mandate and PA2 | `mandate_bounded_delegation.py`, `agent_action_authority.py` | extend, do not replace |
| human decision/currentness/guarded persistence | DS9 contracts/service | certificate consumer and revalidation chokepoint |
| permission/resource/step-up | DS20 Python/Rego owners | retain as narrow floor |
| acquisition approval | `control.py::ingest_data` composition | first candidate consumer |
| CAS/signature/event/audit/idempotency | existing runtime owners | reuse |
| appointments/body constitution/meeting facts | external institution | typed INTEGRATE contracts |
| COI/recusal adjudication | external ethics/governance owner | typed INTEGRATE; absence visible |
| legal/jurisdiction/recognition/effect profiles | incomplete owner chain | later owner decision; no parallel private law engine |
| DS14/Atlas | Atlas owner | projection/consumer, never authority producer |
| individual use | PAO-R4 | separate mandatory boundary |

A research sketch does not appoint the missing canonical owner.

## 8. Later Integration Handoff

### 8.1 Capability chain

| Link | Future responsibility | Current standing |
| --- | --- | --- |
| typed graph/certificate | extend mandate/delegation authority owner with pure contracts | absent |
| institutional-fact producers | external appointment, body/meeting, COI, recognition and legal-profile sources | absent/unappointed |
| reducer | owner-first graph/path/predicate computation | absent |
| persisted artifact/event | CAS graph, certificate/refusal, dependency and invalidation events | absent for INT-R5 |
| orchestration bridge | DS9 pre-effect gateway and guarded store | partial reusable seam |
| enforcement consumer | acquisition first; later DS14 and other protected acts | no complete consumer |
| runtime authorization | DS20 exact permission/resource/step-up | implemented narrower floor |
| verification | red-first corpus, corruption, replay, no-bypass and fault injection | absent |
| surface | REVIEWER/EXPERT/MACHINE through Atlas, PUBLIC only when separately authorized | absent |

### 8.2 Boundary census — operational closure addendum 1

| Function | Owner state | Boundary |
| --- | --- | --- |
| compute/custody PolicyOS certificate | missing implementation owner; PolicyOS OWN candidate | OWN after allocation |
| appointments and office succession | external institution | INTEGRATE/OBSERVE |
| meetings, quorum facts and signatures | external body/meeting system | INTEGRATE |
| conflict declarations/recusal adjudication | external participant and ethics/governance authority | INTEGRATE |
| cross-agency source act | external issuer | INTEGRATE |
| accepting body's recognition decision | external competent accepting body | INTEGRATE |
| permission/resource enforcement | existing DS20 owner | OWN existing narrow floor |
| individual-case crossing | PAO-R4 owner | separate OWN firewall |

### 8.3 Real operator workflow — addendum 2

1. Operator initiates an exact decision/effect request.
2. PolicyOS canonicalizes the request; operator cannot edit the commitment after resolution.
3. The reducer resolves identity/permission, institutional roots/paths, amount, body/forum/quorum,
   separation/COI, recognition and act-effect profiles.
4. Missing holder, owner, adjudicator, provider or decisive evidence returns a typed refusal or
   `not_established` naming the missing role/source and closure route.
5. A positive certificate is shown with scope, limitations, freshness and required next checkpoint.
6. The human decision is recorded through DS9.
7. Immediately before protected effect, the consumer re-resolves every mutable dependency.
8. On revocation/staleness/conflict, the effect is blocked or later dependent effects stop.
9. After hours, no maintainer or requester is borrowed as institutional adjudicator; the case remains
   held/refused until the named external role acts.

### 8.4 State machine — addendum 3

This is an internal artifact lifecycle, not a new product lattice:

```text
requested
  -> resolving
      -> refused [terminal for this request; new evidence opens a new attempt]
      -> not_established [held; reopen on named evidence/appointment/profile]
      -> pre_action_valid
          -> decision_recorded
          -> revalidation_required
              -> effect_authorized
                  -> effect_committed
              -> revoked_before_effect [no effect]
          -> certificate_expired [new evaluation required]

effect_committed
  -> current
  -> invalidated_after_effect
  -> superseded
  -> withdrawn
```

Every transition has event time, legal-effective time where relevant, owner, rule version and public
meaning. Historical states are immutable. `not_established` is not an error; `refused` is a completed
governed result; irreversible effects cannot transition to fictional rollback.

### 8.5 Typed artifacts — addendum 4

Candidate artifacts:

- `DecisionAuthorityGraph`;
- `DelegationValidityCertificate` local result union;
- `AuthorityPredicateReceipt`;
- `AuthorityDependencyEvent`;
- `AuthorityRevalidationReceipt`;
- `AuthorityInvalidationEvent`;
- jurisdiction/body/recognition/act-effect profile refs;
- bounded external assertion adapters.

All remain research candidates and carry explicit authority boundaries.

### 8.6 Edge cases — addendum 5

The fixture pack covers happy path, missing evidence, late and duplicate events, conflicting
authority, owner/adjudicator unavailable, malicious identity alias, degraded provider, partial
success, pre-effect cancellation, honest post-effect non-rollback and historical replay. The five
commissioned adversarial cases are specified to executable Given/When/Then precision.

### 8.7 Tabletop/fault injection — addendum 6

The future chain must kill a provider, corrupt a parent grant, delay/duplicate revocation, remove a
quorum branch, inject late recusal, conflict recognition sources, fail the guarded store and mass
invalidate a root. Success is measured by zero false effects, complete dependency reaction,
idempotency, preserved history and recoverable reconciliation.

### 8.8 OPS-R15 capstone linkage — addendum 7

In the custody-cycle capstone, INT-R5 sits between a proposed/recorded institutional decision and any
protected effect:

```text
external institutional facts
  -> DecisionAuthorityGraph
  -> pre-action certificate or typed refusal
  -> DS9 human decision custody
  -> pre-effect revalidation
  -> DS20-protected effect
  -> dependency monitoring
  -> revalidate / invalidate / supersede / withdraw
```

A succession, revocation, conflict correction, quorum correction or recognition change becomes a
custody event affecting PolicyOS's certificate. The external appointment, meeting, adjudication and
remedy remain outside PolicyOS.

## 9. Promotion And Kill Rules

### 9.1 `research_only`

Current state. The model may inform consolidation and design. It may not be used as capability,
authority grant, legal-sufficiency claim or implementation authorization.

### 9.2 `prototype_allowed`

Allowed only for synthetic/non-protected demonstrations when:

- no external or individual legal effect is possible;
- all missing institutional producers are visible;
- positive outputs are labelled candidate/non-authoritative;
- the five red fixtures and commitment-substitution tests run against the prototype;
- no runtime permission or production approval is opened by the prototype.

### 9.3 `governed_allowed`

Requires:

- approved canonical owner and rule/profile governance;
- typed graph/certificate and all decisive producer contracts;
- persisted graph, certificate/refusal and dependency events;
- DS9 bridge and at least one real protected consumer;
- DS20 operation/resource integration without competence collapse;
- complete semantic, replay, corruption, no-bypass and fault-injection verification;
- one-lattice projection mapping;
- explicit surface/boundary ownership;
- real appointments or honest typed missing-holder results.

### 9.4 `production_candidate`

Additionally requires deployment-jurisdiction legal review, appointed accountable roles, real
institutional sources and SLAs, independent audit, measured revocation/currentness behavior,
operational tabletop, historical replay and a real-world pilot demonstrating false-grant controls.

### 9.5 Blocking conditions

Block a positive certificate or protected effect when any of the following holds:

- decisive field is caller-supplied or only `institutionally_supplied`;
- jurisdiction/body/effect profile is absent or inapplicable;
- required holder, source owner or adjudicator is missing;
- root or path, appointment/succession, amount valuation or scope is not established;
- wrong forum, quorum/vote/co-signature failure;
- self-approval or required separation failure;
- unresolved required conflict/recusal predicate;
- emergency or cross-agency acceptance not established;
- stale certificate or missing checkpoint;
- exact commitment mismatch or replay;
- PAO-R4 is required and not satisfied.

### 9.6 Kill criteria

Withdraw or redesign the mechanism if it:

- produces any false grant in the sealed authority corpus;
- permits requester construction of a positive;
- accepts field presence, role name, minutes conclusion or signature count as authority evidence;
- reuses a certificate across decisions/effects;
- backdates later appointment/ratification;
- loses a revocation dependency or permits post-revocation effect contrary to profile;
- claims no conflict beyond observable/declaration boundaries;
- normalizes jurisdiction disagreements into one hidden default;
- lets a projection or DS20 `allow` mint institutional competence;
- cannot replay the exact historical proposition;
- requires PolicyOS to become administrator, court, meeting operator or institutional appointing
  authority.

## 10. Open Questions For Consolidation

### 10.1 Questions requiring later owner or architect decisions

1. Which existing runtime-quality domain owner formally owns the graph/certificate rather than only
   the current operational envelope?
2. Which component owns versioned jurisdiction/body/recognition/act-effect profiles without creating
   a second Lex or private legal engine?
3. What is the exact DS4 one-lattice projection mapping for local certificate outcomes?
4. Which protected effect is the first complete consumer: acquisition approval, DS14 or another
   authority-bearing operation?
5. Which external institution supplies appointment, body/meeting and conflict facts in the first
   pilot, and what makes their predicates independently reconciled?
6. Who adjudicates contested forum, recusal and emergency predicates when the pilot institution does
   not already have an owner?
7. Which actions have snapshot, lease or checkpoint semantics under the pilot jurisdiction?
8. What is the transaction identity/valuation owner for amount-limited authority?
9. How are mass root invalidations joined to the broader Decision-Validity/custody cascade without a
   parallel invalidation system?
10. What public claim, if any, is justified before real institutional holders exist? The default is
    the typed refusal, not a simulated holder.

### 10.2 Finding classification register

| ID | Classification | Finding | Disposition |
| --- | --- | --- | --- |
| `INT-R5-F01` | repository/process | Required research landed after three named consumers. | record sequencing violation; audit shipped code first |
| `INT-R5-F02` | repository/model | GY-PA2 is internally sound for its five predicates. | reuse as bounded subset |
| `INT-R5-F03` | repository/model | DS9 actor/custodian split, re-resolution and guarded store are sound. | reuse as bridge/consumer |
| `INT-R5-F04` | repository/model | DS20 accurately enforces what/which resource for a verified runtime principal, not institutional competence. | retain boundary |
| `INT-R5-F05` | repository/model | acquisition composition is the closest pre-effect seam. | candidate first consumer |
| `INT-R5-F06` | repository/absence | six of ten required attributes are wholly unrepresentable; four are partial. | full capability absent |
| `INT-R5-F07` | documentation drift | DS20 historical 33-permission prose differs from pinned 34/34 Python/Rego parity. | do not treat as semantic defect |
| `INT-R5-F08` | formal/design result | authority provenance requires typed graph and monotonic attenuation. | adopted in research spec |
| `INT-R5-F09` | information limit | certificate-at-check cannot prove later mutable state. | mandatory freshness/checkpoint semantics |
| `INT-R5-F10` | jurisdiction-dependent rule | quorum, presence, forum defects and cure consequences differ. | mandatory versioned profiles |
| `INT-R5-F11` | control invariant | self-approval is structural and non-waivable in the target baseline. | hard refusal fixture |
| `INT-R5-F12` | information limit | undisclosed/off-system conflicts cannot be disproved. | bounded claim or `not_established` |
| `INT-R5-F13` | boundary result | cross-agency acceptance transfers a narrow assertion, not blanket authority. | `recognised_as` plus negative perimeter |
| `INT-R5-F14` | semantic result | act type follows legal effect/responsibility, not title. | separate act-effect profile |
| `INT-R5-F15` | institutional result | no appointed holder/adjudicator must remain a typed missing-role result. | no model change needed on appointment |
| `INT-R5-F16` | boundary result | PAO-R4 remains independent. | no absorption or substitution |
| `INT-R5-F17` | capability classification | research package is not a live artifact chain. | `absent/unallocated` |
| `INT-R5-F18` | stop-rule result | no merged model was wrong enough to require early architect stop. | complete research; route gaps normally |

### 10.3 Standing on the three W4-K05 axes

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

- **Research standing — `accepted_narrow_scope`:** the model and falsifiers are supported within
  explicitly profiled jurisdictions, sources and information boundaries; no universal legal
  validity theorem is claimed.
- **Capability standing — `absent/unallocated`:** no admitted complete chain or appointed canonical
  owner exists. The shipped components are narrower reusable capabilities; Markdown is not
  `contract_only`.
- **Gate standing — `NO_GO`:** PolicyOS may not issue a positive institutional authority certificate
  or treat it as permission until the promotion conditions are met. This does not gate candidate
  demonstrations or the existing narrower DS20/DS9/GY-PA2 capabilities.

### 10.4 Pattern Pass

| Pattern | Check and result |
| --- | --- |
| `P01` contract-only capability | prevented: research remains `absent/unallocated` |
| `P02` mature fragments without bridge | recorded: PA2/DS9/DS20 are reusable fragments; full bridge absent |
| `P03` internal state without surface | future REVIEWER/EXPERT/MACHINE surface required; none claimed |
| `P04` status proliferation | local result union feeds one lattice; no new global lattice |
| `P05` authority dilution | exact `authoritative_for`/`may_not_use_for`; DS20/projection cannot mint competence |
| `P07` rule-version replay | jurisdiction/body/effect/profile refs and historical/current questions separated |
| `P08` time-role fragmentation | decision, effect, assertion, legal-effective, observed, freshness and replay times separated |
| `P09` soft-gate lifecycle | no warning substitutes for required authority predicate |
| `P10` structural-only validation | real-consumer, effect-count, near-pass, holdout and corruption tests required |
| `P13` contract gravity/ERP | reuses existing owners and integrates sovereign functions; no meeting/court/appointment subsystem |
| `P15` candidate laundering | requester/external assertion cannot become authority without admission |
| `P20` normative choice laundering | jurisdiction/adjudicator decisions remain external and visible |
| `P22` mandate/legitimacy laundering | role/permission is not mandate; full path required |
| `P26` responsibility integrity | operative maker and source/acceptance/decision/execution responsibility separated |
| `P27` parallel owner bypass | extends mandate/DS9/DS20 owners; no second permission system |
| `P29` authorial proof | graph/certificate recomputed; caller cannot author positive; real consumer required |
| `P31` instance patching | one graph/reducer/pre-effect chokepoint intended for the class, not five fixture patches |
| `P32` trust by form | role names, refs, signatures, minutes and assertions require resolve/bind/verify |
| `P33` witness as spec | mutation variants and sealed holdout required |
| `P35` denominator | 10-file executable owner denominator named; index zero not used as proof |
| `P36` inherited warrant | source doctrines transferred by named regime and classification, not surrounding prose |
| `P37` declared predicate | every decisive predicate has producer and admission class; missing producer fails closed |
| `P38` proxy/property divergence | role token vs competence, count vs quorum, title vs effect and signature vs forum explicitly tested |
| `P41` attribution | shipped behavior is attributed to exact owners; historical documentation drift separated from current code |

No pattern-register edit is made from research stage.

### 10.5 Consolidation recommendation

Consolidation should adopt the graph/certificate proposition, producer discipline, exact commitment,
profiled predicates, unappointed-holder refusal, freshness/revalidation contract and red-first
fixtures. It should not directly adopt the candidate field names as final wire schema.

The final architecture decision should preserve the central separation:

```text
DS20: may this verified runtime principal perform this exact operation/resource now?
INT-R5 certificate: did this person/body possess the institutional authority to make this exact decision?
PAO-R4: may this policy-level output cross into an individual case?
```

All three may be required for one protected effect. None substitutes for another.
