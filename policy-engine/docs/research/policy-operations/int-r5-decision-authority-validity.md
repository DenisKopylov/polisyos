---
title: "INT-R5 — Pre-action decision authority proof"
research_id: INT-R5
status: amended_research
kind: deep-research
result_type: accepted_narrow_scope
research_only: true
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r5-amendment
current_repo_baseline: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
package_head_audited: 02e203de90d51280d569e7f641a158569ae4df39
audit_head: 247f89f016f71ee603ed76ef6dbb6403f7e651a0
inspection_date: 2026-08-29
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
repository_verdict: narrow_components_sound_acquisition_composition_claim_withdrawn_full_model_incomplete
selected_authority_slice_files: 10
complete_executable_closure_claimed: false
external_surveys_consumed: 5
external_survey_full_bytes_committed: false
supporting_files:
  - int-r5/repository-baseline.md
  - int-r5/external-evidence-ledger.md
  - int-r5/survey-source-manifest.md
  - int-r5/decision-authority-specification.md
  - int-r5/adversarial-fixtures.md
  - int-r5/amendment-ledger.md
authoritative_for:
  - research-level specification of DecisionAuthorityGraph
  - research-level specification of pre-action DelegationValidityCertificate
  - bounded comparison with pinned selected repository surfaces
  - red-first semantic fixtures and falsifiers
  - later implementation routing and kill criteria
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, API or persistence contract
  - legal-sufficiency conclusion in any jurisdiction
  - institutional appointment or authority grant
  - repository-wide semantic absence claim
  - capability promotion or gate opening
  - individual-case authorization governed by PAO-R4
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
jurisdiction-dependent predicates. The certificate is a reproducible pre-action reduction against an
exact decision, independently established decision time and intended effect. It is neither an approval
asserted by the requester nor an audit record assembled after execution.

### 1.2 Sequencing relationships, corrected

The backlog contains more than one relationship. It requires INT-R5 to land before GY-PA2 or Atlas
DS9/DS14 consumers close, and separately says INT-R5 feeds DS20 vocabulary and acquisition approvals.
The corrected ledger is:

```yaml
closure_order_violations:
  - GY-PA2
  - DS9
unclosed_named_consumer:
  - DS14
missed_feed_dependencies:
  - DS20 action-permission vocabulary
missing_integrations:
  - acquisition -> PA2/DS9 institutional-authority bridge
```

There were **two explicit closure-order violations**, not three identical violations. DS20 is a
separate missed feed; acquisition is a separate missing integration. This correction does not excuse
the sequencing failure. It makes its types and arithmetic accurate.

### 1.3 Requirement-derived model versus shipped model

The model is derived from the requirement and five external surveys before comparison with shipped
fields. Existing code is not silently promoted into the correct authority model merely because it
shipped first.

The comparison now yields four different statements:

1. GY-PA2's declared five-predicate operational core is sound but incomplete for institutional
   authority.
2. DS9's run-bound source/currentness/custody path is sound but incomplete.
3. DS20 is sound within its runtime operation/resource authorization boundary.
4. The prior claim that acquisition already composes DS20 + PA2 + DS9 is **wrong and withdrawn**.
   The production acquisition route is DS20-only; the institutional bridge is missing.

No unsafe universal rule was found inside the three narrow component cores. One false topology claim
was found in the research package itself and corrected by amendment.

### 1.4 False equivalences prevented

This result rejects:

- verified login, role or permission = institutional competence;
- fresh MFA/step-up = valid delegation or appointment;
- signed `HumanDecisionRecord` = valid collegial act;
- board role token = forum, composition, quorum or vote proof;
- disclosed conflict = cured structural self-approval;
- canonical hash of caller input = independently established semantic fact;
- certificate at `t0` = knowledge of every possible authority state at `t1`;
- authenticated external assertion = local recognition/authorization;
- UI verb `approve` = legal classification of the act;
- architectural adjacency = production call edge;
- ten inspected files = complete executable closure;
- INT-R5 certificate = PAO-R4 individual-use pass, or vice versa.

### 1.5 Four-way identity and custody boundary

| Plane | Verdict | PolicyOS responsibility | Boundary retained |
|---|---|---|---|
| computation and custody of PolicyOS's own bounded certificate/refusal | **OWN candidate** | recompute, bind, persist, monitor and replay after allocation | PolicyOS owns its statement, not the office or external power |
| appointment, delegation, body/meeting, COI/recusal, recognition and legal-effect facts | **INTEGRATE** | typed purpose-limited adapters; issuer/content/scope/time verification | external institutions remain source/adjudicator |
| succession and changes in external authority | **OBSERVE** | consume changes because they affect certificate standing | PolicyOS does not conduct succession |
| meetings, appointments, disputed adjudication, execution and remedies | **OUT_OF_SCOPE** | name external owner and refuse when evidence is missing | no court, administrator, meeting operator or appointing authority absorbed |

No role holder is appointed by this research.

### 1.6 PAO-R4 boundary and executable conjunction

PAO-R4 remains the individual-use firewall. INT-R5 proves who or which body had authority to make the
decision. It does not establish individual facts or permit a policy-level artifact to decide an
individual case.

For an individual-case or pointwise-recoverable target, the future effect predicate is conjunctive:

```text
protected effect :=
    current INT-R5 institutional-authority receipt
    ∩ DS20 exact operation/resource/permission/step-up admission
    ∩ PAO-R4 crossing-gate receipt
```

Required negatives:

- valid INT-R5 + failed/missing PAO-R4 -> zero individual effect;
- valid PAO-R4 + failed/missing INT-R5 -> zero protected effect.

Neither owner may infer or mint the other's result.

## 2. Current Repo Baseline

### 2.1 Pin, holder and denominator

```yaml
repository: DenisKopylov/polisyos
pin: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
measurement_holder: INT-R5 stage-1 pass, corrected by stage-3 amendment
selected_slice: int-r5-authority-slice-v1
files: 10
python: 9
rego: 1
complete_executable_closure: false
```

The ten files are a selected authority slice covering named PA2, DS9, DS20 and acquisition
coordinates. They are **not** a complete import/call/route/producer/consumer closure. Known positive
controls outside the slice include the real human-decision route, production-approval resolver,
acquisition effect service and transitive identity/security/event/store owners.

Accordingly:

```text
absence in selected ten-file slice: established where all ten were read
absence in complete executable/authority closure: not established by this research
```

Search-index zeroes remain orientation only.

### 2.2 Shipped component verdicts

| Component | What the inspected path proves | Amended verdict |
|---|---|---|
| `GY-PA2` | verified identity, explicit permission, mandate-bounded delegation, operation/envelope match and live accountability with operation/resource/subject/tenant/time/status binding | **sound within declared predicates; incomplete for INT-R5** |
| `DS9` | actor/custodian separation, strict source union, raw-source re-resolution, currentness, narrow reviewer separation, guarded persistence/readback | **sound on run-bound human-decision path; incomplete for INT-R5** |
| `DS20` | verified principal, exact permission, operation, resource, authorization source and signed replay-protected step-up | **sound within runtime authorization boundary** |
| acquisition route | `EVIDENCE_ACQUIRE`, request-bound `runtime.evidence.acquisition`, `ACQUISITION_APPROVAL`, then `run_data_ingestion` | **DS20-only today; PA2/DS9 institutional bridge missing** |

The acquisition route/service contains no PA2 resolver, `HumanDecisionService`, human-decision record,
reviewer-separation receipt or DS9 guarded authority/currentness write. DS9's PA2 arm exists on a
separate route; it is a reusable candidate seam, not a landed acquisition composition.

### 2.3 Permission parity

At the pin:

```yaml
RuntimePermission: 34
Rego permission_vocabulary: 34
set_equality: true
```

The historical DS20 prose count of 33 predates `runs.human_decisions.create`; it is documentation
drift, not current parity failure.

### 2.4 Ten-attribute observation table

`observed_fragment` means a narrower enforced predicate exists in the selected slice.
`not_observed_in_selected_slice` is a bounded non-observation, not a repository-wide zero.

| Required attribute | Observation | Positive coordinate | Missing/unsettled proposition |
|---|---|---|---|
| temporal and subject-matter delegation | `observed_fragment` | `DelegatedActionEnvelope`; PA2 currentness | source law, jurisdiction, amount, reserved matters, full purpose scope |
| quorum and co-signature | `not_observed_in_selected_slice` | role labels only | body/forum, roster, timeline, threshold, votes, signature purpose |
| separation of duties | `observed_fragment` | DS9 `ReviewerSeparationCredential` | full lineage and controlling-subject closure |
| recusal and conflict of interest | `not_observed_in_selected_slice` | none in slice | disclosure, detection, recusal, waiver/management and bounded producer |
| acting appointments and succession | `not_observed_in_selected_slice` | principal/role only | office, vacancy, basis, succession, qualification, predecessor path |
| subdelegation limits | `not_observed_in_selected_slice` | none in slice | parent grant, permission/depth, class, attenuation, creation-time power |
| expiry and emergency authority | `observed_fragment` | envelope time/status | emergency source, trigger, necessity/urgency, scope and end condition |
| revocation mid-operation | `observed_fragment` | DS9 pre-use currentness | checkpoint/effect semantics; absent on acquisition route |
| cross-agency acceptance | `not_observed_in_selected_slice` | authentication fragments | gateway, accepted assertion, negative perimeter, refusal grounds, duties |
| consultation/recommendation/approval/binding decision | `not_observed_in_selected_slice` | workflow labels | legal effect, condition precedent, freedom to depart, operative maker |

```yaml
observed_fragment: 4
not_observed_in_selected_slice: 6
full_INT_R5_representation: 0
repository_wide_zero_claims_from_table: 0
```

### 2.5 Capability standing

The full capability is `absent/unallocated`: no admitted production graph/certificate, allocated
complete owner, institutional producer chain, graph reducer, enforcing acquisition/other consumer or
semantic end-to-end chain exists. This conclusion does not depend on pretending the six slice
non-observations are repository-wide zeroes.

## 3. External Research Baseline

### 3.1 Source custody

The exact five survey identities, SHA-256 digests, line/byte denominators, external file versions,
claim anchors and admitted extracts are in
[`int-r5/survey-source-manifest.md`](int-r5/survey-source-manifest.md).

A branch reader can replay every transferred claim against package-local extracts and exact source
identity. Full original survey byte verification still requires the external artifact matching the
manifest digest. This is an explicit residual, not a bibliography presented as full custody.

### 3.2 Transfer discipline

The surveys are external practice, never repository capability or authority. Legal material retains
its jurisdiction and source class. External terms are not silently registered as PolicyOS vocabulary.
Public-law and corporate-governance disagreements remain visible because remedies differ.

High-confidence transfers:

- role/delegation alone is insufficient;
- child authority is attenuated and creation-time parent power matters;
- amount is an economic-transaction valuation rule;
- acting, succession, implied authorization, emergency and cure are distinct provenance paths;
- legal organ/forum is separate from physical membership;
- quorum is item- and profile-relative and requires event evidence;
- co-signature is independent of quorum;
- structural self-approval is not cured by disclosure;
- undisclosed/off-system conflicts cannot be disproved;
- pre-action proof is relative to admitted state and cannot know a future event;
- cross-agency acceptance is purpose-limited and preserves a negative perimeter;
- act type follows legal effect and responsibility, not title;
- cure may be prospective, relation-back, saved, limited, forbidden or unresolved by profile.

### 3.3 Preserved disagreements

No universal answer is created for:

- void/voidable/saved/curable/non-ratifiable consequences;
- quorum denominator, persistence or remote presence;
- title defects and saving rules;
- mandatory, manageable and waivable conflict grounds;
- snapshot, lease or checkpoint treatment;
- recognition residual duties;
- preparatory versus binding approval;
- prospective versus relation-back cure effect.

Unknown mandatory profile or unresolved adjudication cannot yield a positive.

## 4. Result

### 4.1 Result type

**`accepted_narrow_scope`.** The research supports a jurisdiction-profiled pre-action proof with exact
commitment, graph reduction, event-sourced collegial evidence, transaction-level separation, bounded
conflict claims, purpose-limited recognition and explicit freshness/cure semantics. It does not
support a universal legal-validity Boolean, repository-wide semantic zero or production claim.

### 4.2 Correct information-limit proposition

Mutable authority does not imply actual change. An unchanged history may have equal authority at
`t0` and `t1`.

The defensible proposition is:

```text
there exist histories H0 and H1 such that
observations(H0, <= t0) = observations(H1, <= t0)
but authority(H0, t1) != authority(H1, t1), t1 > t0
```

A certificate computed from `t0` evidence cannot distinguish those futures and cannot determine
`t1` authority across all admissible histories. This is a non-inferability proposition, not a theorem
that inequality occurs in every history.

The consequence remains: record `as_of`, `fresh_until`, mutable dependencies and one profile-derived
mode — snapshot, issuer-authorized lease, revalidate-before-commit or continuous checkpoints.

### 4.3 `DecisionAuthorityGraph`

The graph binds one exact decision/effect and preserves typed nodes/edges for:

- source power, jurisdiction/profile applicability, institution, office, principal and appointment;
- delegation, subdelegation, succession/acting, implied/agency and emergency paths;
- amount valuation and place/subject scope;
- body, forum, session, item, participation, vote, quorum and co-signature;
- transaction roles, conflict records and recusal/management decisions;
- recognition rule/external act and act-effect classification;
- revocation/invalidation and cure effect.

No generic `AUTHORIZED_BY`, `TRUSTED` or undifferentiated `APPROVED_BY` replaces these distinctions.

### 4.4 Independent producers and canonicalization

Every decisive semantic coordinate has a producer distinct from the requester:

| Coordinate | Required semantic producer |
|---|---|
| decision time | constitutive decision-event system; trusted timestamp where required |
| issued/as-of time | PolicyOS custody event plus trusted time where profile requires |
| effect/commit time | protected-effect ledger/consumer event |
| effect class | versioned operation/effect classification owner |
| jurisdiction/profile applicability | competent profile-governance role plus independent resolver |
| revalidation mode | reducer derived from admitted profile, revocability and effect class |
| decision fields | authoritative transaction/case/decision source per field |
| all institutional predicates | named external/system producers and verifiers in the specification |

Canonicalization proves deterministic bytes and detects mismatch. It does not make a caller-selected
value semantically authoritative. A valid hash with non-positive provenance remains non-positive.

### 4.5 Path reduction

Each candidate path is validated root-to-actor/body. Issuer continuity, signature, creation-time
power, delegation permission, activation, currentness and understood constraints are verified.
Effective scope and validity are intersections. A child cannot amplify a parent. One invalid path
does not destroy an independent valid path, but threshold/conjunction requirements are recomputed.

### 4.6 Collegial, separation and conflict predicates

Collegial validity is per exact decision item and profile. Forum is resolved before quorum. Quorum
uses lawful seats/holders, item-specific eligibility and an event timeline. Vote and co-signature are
separate.

Role comparisons use controlling subject, not account. Configured self-approval is a structural hard
failure. Conflict conclusions distinguish record-established, record-indicated, current declaration,
required adjudication and undisclosed/off-system facts. The certificate never claims psychological
neutrality or absence of undisclosed conflicts.

### 4.7 Cross-agency and act effect

Acceptance verifies legal gateway, source identity/competence, act type/status, purpose/scope,
authenticity/assurance, refusal grounds, retained duties and responsibility allocation. It stores both
`recognised_as` and `not_recognised_as`.

Act effect records formal type, binding effect, condition precedent, freedom to depart, reasons,
legal consequences, operative act, ultimate maker, reviewability and practical departure cost.

### 4.8 `DelegationValidityCertificate`

The certificate carries:

- exact decision/effect commitment;
- independent time receipts;
- graph/root and applicable profile receipts;
- surviving paths and effective scope/validity;
- predicate receipts with producer, provenance, evidence and freshness;
- every mutable dependency;
- local result `pre_action_valid | refused | not_established | not_applicable`;
- namespaced/versioned candidate reason IDs;
- missing role/owner refs and bounded limitations;
- custody computation proof and explicit `authoritative_for`/`may_not_use_for`.

The local result union feeds the existing system lattice. It does not create a second global lattice.

### 4.9 Reason identity and crosswalk

Candidate reason identity shape:

```text
polisyos.int_r5.reason.<slug>@0.1.0-candidate
```

Bare uppercase fixture tokens are withdrawn. The INT-R5 candidate
`polisyos.int_r5.reason.certificate_stale@0.1.0-candidate` is recorded as a semantic sibling — not an
alias — of live `polisyos.eval_safety.certificate_stale@1.0.0` until the owning registry ratifies a
crosswalk. Mapping may never upgrade `not_established` or `refused` to positive.

### 4.10 Unappointed-holder behavior

With no qualifying holder:

```yaml
local_result: not_established
reason_ids:
  - polisyos.int_r5.reason.missing_appointed_holder@0.1.0-candidate
missing_role_or_owner_refs: [exact required role]
```

This is normal typed output. Candidate/demo and negative replay remain available. Later appointment
changes evidence, not model/schema. A team, maintainer, runtime role or adjacent signer cannot be
substituted.

### 4.11 Cure and historical replay

The original certificate is immutable evidence of what was established at its `as_of`. A later cure
is a new event/result carrying:

```text
prospective | relation_back | saved_act | limited | unresolved
```

plus `legally_effective_from`, effect scope and `historical_certificate_mutated: false`. Relation back
is representable where a named profile supplies it; no universal relation-back or no-relation-back
rule is encoded.

## 5. Counterexamples And Failure Modes

The detailed red-first suite is
[`int-r5/adversarial-fixtures.md`](int-r5/adversarial-fixtures.md).

| Required fixture | Unsafe conclusion | Required result |
|---|---|---|
| self-approval | disclosure/two accounts create independence | namespaced self-approval/SoD refusal; zero effect |
| expired delegation | current permission or caller-backdated time revives grant | authoritative event time used; expired path refused |
| wrong forum | correct people/signatures convert committee into board | forum refusal before quorum rescue |
| quorum loss | opening quorum remains true | item/profile recomputation; zero effect where threshold fails |
| post-hoc authorization | later grant mutates original history | original refusal immutable; separate profile-specific cure result |

Additional producer attacks:

- caller backdates decision time;
- caller downgrades irreversible effect;
- caller profile-shops;
- caller requests snapshot while profile requires checkpoint;
- canonical hash is valid but semantic provenance is non-positive.

PAO-R4 attacks run in both directions. Acquisition topology fixture requires the real route/call edge;
calling a separate DS9 service does not prove acquisition integration.

Other failures include split amount, widened child grant, invalid succession root, requester-only
emergency, blanket external trust, recommendation auto-execution, commitment substitution, source
provider degradation, late quorum/recusal/revocation event and current-state historical replay.

## 6. Benchmark Or Fixture Proposal

### 6.1 Corpus

The public pack contains mandatory fixtures, all profile variants, valid near-passes, decisive-field
mutations, producer-substitution attacks, unappointed-holder, cross-agency negative perimeter,
title-versus-effect, PAO-R4 two-direction and acquisition-missing-bridge cases.

A sealed holdout changes names, edge order, titles, aliases and harmless metadata and includes
structurally novel equivalents. Labels concern authority admissibility under declared profiles, not
ultimate legal truth.

### 6.2 Metrics

```text
false_grant
false_refusal
wrong_reason_identity
missed_dependency
stale_certificate_use
commitment_replay_or_substitution
profile_collapse
post_hoc_backdating
unbounded_conflict_claim
PAO_R4_substitution
caller_fact_upgrade
```

`false_grant` is primary. A pass caused by absence of a real producer, bridge or consumer is vacuous.

### 6.3 Test shape and fault injection

Each fixture must exercise the real reducer, persistence/currentness bridge and protected consumer;
assert exact effect count; read back graph, output and dependency events; run a near-pass and
mutations; prove no sibling bypass; and corrupt producer evidence/profile/time/commitment.

Fault injection includes provider loss before effect, delayed/duplicate/out-of-order revocation,
corrupted parent grant, removed quorum branch, late recusal, conflicting recognition, guarded-store
failure, profile change and mass root invalidation. Recovery must fail closed, remain idempotent,
preserve history and execute no effect without final currentness.

## 7. Artifact Contract Sketch

### 7.1 Candidate artifacts

- `DecisionAuthorityGraph`;
- `DelegationValidityCertificate` local result union;
- `AuthorityPredicateReceipt`;
- `ProfileApplicabilityReceipt`;
- `EffectClassificationReceipt`;
- `AuthorityDependencyEvent`;
- `AuthorityRevalidationReceipt`;
- `AuthorityInvalidationEvent`;
- `CureEffectReceipt`;
- jurisdiction/body/recognition/act-effect profile refs;
- bounded external assertion adapters.

All remain research candidates.

### 7.2 Common evidence contract

Every decisive fact carries claim identity/type, subject, typed assertion, source jurisdiction,
governing instrument/rule version, named producer role/instance, issuer/source class, P37 provenance,
verifier receipts, legal/observed/freshness times, evidence refs and authority boundary.

`institutionally_supplied`, `consumer_asserted` and `not_established` are non-positive until the
relevant verifier recomputes or independently reconciles the gate predicate.

### 7.3 Producer discipline

The requester may provide candidates but cannot produce decision/effect time, effect classification,
profile applicability, revalidation mode, appointment, authority path, amount aggregate, quorum,
conflict determination, recognition result, act effect or positive certificate.

Missing producer or adjudicator returns a namespaced typed negative; it does not fall back to caller
input.

### 7.4 One-lattice rule

Certificate local results and family reasons project through the existing status architecture. DS4 or
successor owns mapping. Candidate reason IDs are namespaced/versioned and remain distinct from live
family codes until ratified.

### 7.5 Source-custody contract

`survey-source-manifest.md` records exact source identity and admitted extracts. It does not claim the
external full survey files are committed. Future stages must either retain this explicit residual or
admit the matching full bytes under ordinary evidence custody; they may not replace it with an
unanchored bibliography.

## 8. Later Integration Handoff

### 8.1 Capability chain

| Link | Future responsibility | Current standing |
|---|---|---|
| graph/certificate contracts | extend mandate/delegation authority domain after allocation | absent |
| institutional fact producers | appointments, body/meeting, conflict, recognition and profiles | absent/unappointed |
| reducer | graph/path/predicate computation with producer discipline | absent |
| persistence/dependency | graph, result, receipts and invalidation events | absent for INT-R5 |
| human-decision/currentness bridge | DS9-like source re-resolution and guarded custody | reusable seam, not acquisition-wired |
| PAO-R4 crossing | separate receipt for individual/pointwise use | delivered separate boundary; future conjunction missing |
| runtime enforcement | DS20 exact permission/resource/step-up | implemented narrow floor |
| acquisition consumer | bridge before `run_data_ingestion` | missing |
| Atlas/DS14 projection | reviewer/expert/machine projection | unstarted/future consumer |
| verification | semantic corpus, corruption, replay, no-bypass and fault injection | absent |

### 8.2 Correct acquisition handoff

```text
exact acquisition decision/effect commitment
  -> INT-R5 graph/certificate/currentness
  -> PAO-R4 receipt if target crosses individual-use boundary
  -> DS20 EVIDENCE_ACQUIRE/resource/step-up
  -> run_data_ingestion
```

At the baseline only the final DS20-to-ingestion portion exists. The missing bridge is named
`acquisition_authority_bridge` as a research placement, not an implemented owner.

### 8.3 Operator workflow

1. Operator initiates an exact decision/effect candidate.
2. Field-specific producers resolve semantic facts; canonicalization commits admitted values.
3. Applicability resolver selects jurisdiction/body/effect profiles; requester cannot profile-shop.
4. Reducer resolves identity, roots/paths, amount, forum/quorum, SoD/COI, recognition and effect.
5. Missing holder, producer, adjudicator or evidence yields typed `not_established`/refusal.
6. Positive certificate shows exact scope, source boundary, limitations and freshness.
7. Human decision is recorded through a governed custody path.
8. Conditional PAO-R4 receipt is obtained when required.
9. Immediately before effect, mutable dependencies are re-resolved.
10. DS20 enforces exact operation/resource/step-up and the effect consumer evaluates the conjunction.
11. Revocation or correction blocks the effect or stops later dependencies; history is preserved.

No maintainer or requester is borrowed as institutional adjudicator after hours.

### 8.4 Lifecycle and typed outcomes

The lifecycle is internal artifact state, not a new product lattice:

```text
requested -> resolving
  -> refused
  -> not_established
  -> pre_action_valid
      -> decision_recorded
      -> revalidation_required
          -> PAO_R4_required/received where applicable
          -> effect_authorized
          -> effect_committed
      -> revoked_before_effect
      -> certificate_expired

effect_committed -> current | invalidated_after_effect | superseded | withdrawn
```

Every transition records event time, legal-effective time where applicable, producer, profile/rule and
meaning. Irreversible effects never transition to fictional rollback.

### 8.5 Boundary census

| Function | Owner state | Boundary |
|---|---|---|
| compute/custody PolicyOS certificate | missing implementation owner; PolicyOS OWN candidate | OWN only after allocation |
| decision/effect time and source fields | external/source systems plus protected-effect ledger | INTEGRATE/OWN by field |
| appointments and succession | external institution | INTEGRATE/OBSERVE |
| meetings/quorum/signatures | external body/meeting system | INTEGRATE |
| conflict declarations/adjudication | participant and ethics/governance authority | INTEGRATE |
| recognition/act-effect profiles | external legal/governance sources plus applicability owner | INTEGRATE |
| permission/resource enforcement | DS20 | existing OWN narrow floor |
| individual-use crossing | PAO-R4 | separate OWN firewall |
| projection | Atlas/DS14 | consumer only |

### 8.6 OPS-R15 capstone linkage

```text
external institutional facts
  -> DecisionAuthorityGraph
  -> certificate or typed negative
  -> governed decision custody/currentness
  -> conditional PAO-R4 crossing
  -> DS20-protected effect
  -> dependency monitoring
  -> revalidate / invalidate / supersede / withdraw / cure-effect record
```

The external appointment, meeting, adjudication and remedy remain outside PolicyOS.

## 9. Promotion And Kill Rules

### 9.1 Research-only

Current state. The model may inform consolidation and design. It cannot be used as capability,
authority grant, legal-sufficiency claim or implementation authorization.

### 9.2 Prototype allowed

Only synthetic/non-protected demonstrations with no external/individual legal effect, visible missing
producers, candidate/non-authoritative positives, red fixtures and no opening of runtime permissions or
production approvals.

### 9.3 Governed allowed

Requires approved owner/profile governance; typed contracts; independent producers for every decisive
field; persisted result/dependencies; real bridge and protected consumer; conditional PAO-R4
conjunction; DS20 integration; registered reason/status crosswalk; complete semantic/replay/corruption/
no-bypass/fault verification; and honest holder absence behavior.

### 9.4 Production candidate

Additionally requires deployment-jurisdiction legal review, appointed roles, real institutional
sources/SLAs, independent audit, measured currentness/revocation behavior, operational tabletop,
historical replay and real-world pilot false-grant evidence.

### 9.5 Blocking conditions

Block positive/effect when:

- any decisive fact is caller-supplied or non-positive;
- decision/effect time lacks an authoritative receipt;
- effect class/profile applicability/revalidation mode is caller-selected;
- required profile, holder, producer or adjudicator is missing;
- root/path, appointment, amount, scope, forum, quorum, vote or co-signature fails;
- self-approval or required separation fails;
- required conflict/recusal, emergency, recognition or act-effect predicate is unresolved;
- certificate is stale or checkpoint missing;
- commitment/replay mismatch exists;
- PAO-R4 is required and missing/failed;
- the protected consumer does not actually invoke the complete conjunction.

### 9.6 Kill criteria

Withdraw/redesign if the mechanism:

- produces a false grant in the sealed corpus;
- permits requester construction of a positive;
- treats canonical bytes as semantic authority;
- accepts role name, minutes conclusion, signature count or authenticated assertion as authority;
- reuses a certificate across decisions/effects;
- backdates an original certificate or denies relation-back regimes universally;
- loses revocation dependencies;
- claims absence of undisclosed conflicts;
- hides jurisdiction disagreement in a default;
- lets DS20, Atlas, PAO-R4 or projection mint a different predicate;
- cannot replay historical state;
- calls adjacency a production call edge;
- calls a selected slice a complete closure;
- creates a second global status lattice or strips reason namespace/version;
- requires PolicyOS to become court, appointing authority, meeting operator or administrator.

### 9.7 Standing non-movement

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

The amendment changes research text only. It does not implement, allocate, appoint, register, publish
or open a gate.

## 10. Open Questions For Consolidation

### 10.1 Owner and architecture questions

1. Which existing domain formally owns graph/certificate contracts after allocation?
2. Which owner governs jurisdiction/body/recognition/act-effect profiles without a private legal
   engine?
3. Who independently produces decision time and effect classification in the first consumer?
4. Which component owns profile applicability resolution?
5. What exact registered status/reason crosswalk replaces candidate IDs?
6. Which component evaluates the INT-R5 ∩ PAO-R4 ∩ DS20 conjunction?
7. Which protected effect is first: acquisition, DS14 or another operation?
8. Which pilot institutions supply appointment, meeting and conflict facts?
9. Who adjudicates disputed forum, recusal, emergency and cure effect?
10. What transaction/valuation owner supplies amount authority?
11. How are mass root invalidations joined to the custody cascade?
12. Will full survey bytes be admitted to repository custody, or will the manifest residual remain?

### 10.2 Corrected finding classification

| ID | Classification | Current finding | Disposition in amended package |
|---|---|---|---|
| `INT-R5-F01` | repository/process | two closure-order violations plus separate DS20 feed/acquisition integration drift | corrected relationship ledger |
| `INT-R5-F02` | repository/model | GY-PA2 narrow core sound/incomplete | retain bounded subset |
| `INT-R5-F03` | repository/model | DS9 run-bound seam sound/incomplete | retain candidate bridge |
| `INT-R5-F04` | repository/model | DS20 narrow floor sound | retain boundary |
| `INT-R5-F05` | repository/topology | acquisition production composition claim was wrong | withdrawn; bridge named missing |
| `INT-R5-F06` | repository/measurement | four fragments and six non-observations in selected slice | no repository-wide zero claimed |
| `INT-R5-F07` | documentation drift | historical 33 versus current 34/34 | retained as drift |
| `INT-R5-F08` | formal/design | typed graph and attenuation required | retained |
| `INT-R5-F09` | information limit | future authority not inferable from `t0` evidence across all histories | corrected quantifier |
| `INT-R5-F10` | jurisdiction rule | quorum/forum/cure differ | profiles required |
| `INT-R5-F11` | control invariant | structural self-approval | retained red fixture |
| `INT-R5-F12` | information boundary | off-system conflicts cannot be disproved | bounded claim retained |
| `INT-R5-F13` | boundary | cross-agency acceptance is narrow | negative perimeter retained |
| `INT-R5-F14` | semantic | act type follows effect/responsibility | retained |
| `INT-R5-F15` | institutional | no holder/adjudicator remains typed negative | retained |
| `INT-R5-F16` | boundary | PAO-R4 independent and conjunctive where applicable | corrected handoff |
| `INT-R5-F17` | vocabulary | candidate reasons require namespace/version/crosswalk | corrected |
| `INT-R5-F18` | source custody | exact identities/anchors committed; full bytes external | explicit residual |
| `INT-R5-F19` | capability | complete chain absent | `absent/unallocated` |

### 10.3 W4-K05 standing

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

### 10.4 Pattern Pass

| Pattern | Amended check |
|---|---|
| `P01` | research remains absent/unallocated, not contract-only |
| `P02` | PA2/DS9/DS20 are fragments; acquisition bridge is explicitly missing |
| `P03` | no surface capability claimed |
| `P04` | local union and namespaced reasons feed one lattice; crosswalk owner remains external |
| `P05` | exact boundaries; no component mints another predicate |
| `P07` | profile/rule version and historical/current questions separated |
| `P08` | decision, issue, effect, legal-effective, observed and freshness times separated |
| `P09` | no warning substitutes for failed authority |
| `P10` | real producer/bridge/consumer/effect-count tests required |
| `P13` | reuses owners; no court/meeting/appointment subsystem |
| `P15` | caller/external assertion cannot be laundered through canonicalization |
| `P20` | profile/adjudication choices remain visible |
| `P22` | role/permission not mandate |
| `P26` | source, acceptance, final decision and execution responsibility separated |
| `P27` | no parallel permission or PAO-R4 system |
| `P29` | every decisive field has producer; requester cannot author positive |
| `P31` | one class mechanism, not fixture patches |
| `P32` | form/role/signature/minutes require resolution and verification |
| `P33` | near-pass, mutation and holdout retained |
| `P35` | ten-file denominator narrowed; no complete closure or repo-wide zero claimed |
| `P36` | survey identities and claim anchors explicit; full-byte residual explicit |
| `P37` | producer/provenance for each decisive predicate |
| `P38` | role/competence, count/quorum, title/effect, hash/semantic fact and adjacency/call edge tested |
| `P41` | shipped behavior attributed to exact owners; history and current state separated |

No pattern-register edit is made.

### 10.5 Consolidation recommendation

Consolidation may consume the graph/certificate proposition, independent-producer discipline, exact
commitment, profiled predicates, typed missing-holder output, namespaced candidate reason design,
freshness/cure semantics and red fixtures. It must not consume the withdrawn acquisition composition,
complete-ten-file-closure claim or universal inequality.

The final separation remains:

```text
DS20: may this verified runtime principal perform this operation/resource now?
INT-R5: did this person/body possess institutional authority for this exact decision?
PAO-R4: may this policy-level artifact cross into this individual case?
```

All may be required. None substitutes for another.
