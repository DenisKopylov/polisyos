---
title: "INT-R5 — Pre-action decision authority proof"
research_id: INT-R5
status: in_progress_research
kind: deep-research
research_only: true
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r5-research
current_repo_baseline: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
inspection_date: 2026-08-29
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
repository_verdict: shipped_model_sound_but_materially_incomplete
authoritative_for:
  - research-level specification of a DecisionAuthorityGraph
  - research-level specification of a pre-action DelegationValidityCertificate
  - bounded comparison of that specification with the pinned shipped repository
  - red-first semantic fixtures for later implementation
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
`DelegationValidityCertificate`. The graph preserves authority provenance and the
jurisdiction-dependent predicates. The certificate is a reproducible pre-action reduction of that
graph against an exact decision commitment and evaluation time. It is not an approval entered by
the requester and not an audit trail assembled after execution.

### 1.2 Why this remains research-first after the sequencing failure

The backlog ordered `INT-R5` before `GY-PA2`, Atlas `DS9` and `DS14`, the DS20 vocabulary and
acquisition approvals. At the pinned baseline, `GY-PA2`, `DS9` and `DS20` have already shipped and
the acquisition-approval path already composes their primitives. The sequencing failure does not
convert shipped behavior into the correct model. This pass therefore keeps two objects separate:

1. **Requirement-derived model** — derived from the question, the identity decision and the five
   external surveys without accepting shipped fields merely because they exist.
2. **Repository comparison** — a later mapping from shipped predicates to that model, including
   explicit absences and any contradiction.

The stop rule was whether a shipped component encoded a materially wrong authority rule requiring
an architect ruling before the specification could continue. No such contradiction was found. The
shipped controls are sound inside their declared operational boundaries. They are materially
incomplete as proof of institutional decision authority.

### 1.3 False production claims this result prevents

This result prevents the following false equivalences:

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

### 1.4 Four-way identity-boundary verdict

This task is adjudicated against
`docs/system-design-decisions/policyos-identity-and-custody-boundary.md`:

| Plane | Verdict | PolicyOS responsibility | Boundary retained |
| --- | --- | --- | --- |
| Pre-action computation and custody of PolicyOS's own authority-validity statement | **OWN** | Recompute the graph reduction, bind it to the exact decision/effect, persist the proof or typed refusal, monitor dependencies that can make the statement stale, and preserve replay. | PolicyOS owns its certificate, not the office, meeting or legal power described by it. |
| Appointments, delegation instruments, quorum records, conflict declarations, recusal determinations, recognition and legal-effect rules | **INTEGRATE** | Define typed, purpose-limited, fail-closed evidence interfaces; verify issuer, signature, scope, currentness and rule-profile applicability. | External institutions remain the source and adjudicator of their acts. |
| Institutional succession and changes in who answers for an external authority assertion | **OBSERVE** | Consume succession/change events because they can freeze or invalidate PolicyOS's certificate. | PolicyOS does not manage the institution or appoint the successor. |
| Conducting meetings, deciding disputed recusals, appointing office-holders, creating legal effect, executing administrative acts and operating remedies | **OUT_OF_SCOPE** | Name the external owner and refuse when required evidence is unavailable. | No administrator, court, case-management or executor role is absorbed. |

This extends the identity decision's existing pattern: own the typed evidence contract and the
reaction of PolicyOS's signature; integrate or observe the sovereign function.

### 1.5 PAO-R4 boundary

`PAO-R4` remains the individual-use firewall. `INT-R5` answers **who or which body had authority to
make a decision**. It does not establish individual facts, decide whether a policy-level artifact
may be applied to an individual, or authorize an individual outcome. A valid
`DelegationValidityCertificate` cannot substitute for the `PAO-R4` crossing gate, and a `PAO-R4`
pass cannot establish the decision-maker's competence.

### 1.6 Result in one sentence

**The repository's shipped model is sound but materially incomplete: it can prove a verified
runtime principal had a current, resource-bound permission and a bounded human-decision mandate for
a protected operation, but it cannot yet prove the full institutional proposition that the person
or body had authority to make this exact decision.**

## 2. Current Repo Baseline

### 2.1 Pin, measurement holder and limitations

- Repository: `DenisKopylov/polisyos`
- Pinned baseline: `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`
- Research branch: `research/int-r5-research`
- Step-0 skeleton commit: `000573d25bf3f38bdd8042e59f5ab4a1e59ab0c1`
- Inspection holder: this INT-R5 research pass, using exact GitHub reads at the pinned commit.
- Local-network limitation: ordinary local `git push` failed DNS resolution. Repository reads and
  writes therefore use the authenticated GitHub connector. No workflow or transport workaround is
  used.

Set-level claims below either name the complete canonical-owner denominator inspected or are quoted
as historical receipts from the component's closure record. GitHub search-index zeroes are
orientation only and are not treated as complete-tree zeroes.

### 2.2 Mandatory documents inspected

The baseline included:

- root `AGENTS.md` and `policy-engine/CONTRIBUTING.md`;
- `docs/reference/policy-operations-research-pipeline.md`;
- `docs/research/policy-operations-and-real-world-runtime-backlog.md`;
- `docs/system-design-decisions/policyos-identity-and-custody-boundary.md`;
- `universal-policy-design-system-vision-and-organizing-rules.md`;
- `universal-policy-design-target-architecture-and-gap.md`;
- `policy-design-best-in-class-operating-model.md`;
- `honest-diagnostics-substrate.md`;
- `policy-design-causal-operating-system-north-star.md`;
- `docs/reference/policy-design-case-failure-patterns.md`;
- the GY and Atlas active plans;
- `docs/research/deep-research-value-distillation.md`;
- `docs/system-design-decisions/wave4-decision-evidence-ratification.md`;
- `docs/research/policy-operations/pao-r4-individual-decision-firewall.md`.

The detailed coordinate ledger is in
[`int-r5/repository-baseline.md`](int-r5/repository-baseline.md).

### 2.3 Canonical shipped chain inspected

The canonical-owner denominator for the shipped authority path is **10 files: nine Python owners and
one Rego mirror**, all read at the pinned commit:

1. `src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py`
2. `src/polisyos/runtime/quality/agent_action_authority.py`
3. `src/polisyos/runtime/http/services/human_decision_contracts.py`
4. `src/polisyos/runtime/http/services/human_decisions.py`
5. `src/polisyos/runtime/http/authorization.py`
6. `src/polisyos/runtime/http/resource_binding.py`
7. `src/polisyos/runtime/http/step_up.py`
8. `src/polisyos/runtime/http/permissions.py`
9. `src/polisyos/runtime/http/routes/control.py`
10. `ops/policy/policies/action_permission.rego`

The comparison also consumed the GY-PA2 journal, DS9 plan/journal and DS20 closure record. Those
records do not substitute for the executable owners.

### 2.4 What GY-PA2 actually encodes

`src/polisyos/runtime/quality/agent_action_authority.py` owns a five-predicate operational
authorization decision:

```text
verified_identity
∩ explicit_permission
∩ mandate_bounded_delegation
∩ operation_in_envelope
∩ live_accountability
```

It binds operation, invocation and intent identity, the resource and contract digest, a DS20
permission snapshot, a mandate/delegation envelope and a human-decision request. It refuses
ambiguous or mismatched delegation, subject, tenant and resource bindings. Its accountability check
rejects an envelope that is revoked, not yet valid, expired or incompatible with the current runtime
role.

The strict envelope binds:

- case and mandate-owner references;
- action kind and versioned operation identity;
- required `RuntimePermission`;
- authorized subject and runtime roles;
- tenant and resource digest;
- `valid_from`, `valid_until` and `active|revoked`;
- issuance, provenance and rule-version references.

This is a sound operational mandate gate. It is not a complete authority chain. It carries no
jurisdictional rule profile, source-law power, amount/valuation rule, parent delegation, right to
subdelegate, acting/succession provenance, forum, quorum, co-signature, recusal determination,
cross-agency recognition or legal-effect classification.

**Verdict: sound but incomplete.**

### 2.5 What DS9 actually encodes

`src/polisyos/runtime/http/services/human_decision_contracts.py` and
`human_decisions.py` distinguish the authenticated human actor from the PolicyOS custody signer.
They bind:

- issuer-qualified principal identity, key, roles, permissions and validity;
- a signed reviewer-separation credential naming the reviewed actor or actors;
- the exact decision request and evidence exposure;
- a presentation contract and verifier epoch;
- a strict source-kind union (`agent_action_authority` or `production_approval`);
- currentness at recording and again at operational consumption;
- CAS identity, append-only event evidence, reservation/idempotency and guarded persistence.

Operational consumers re-resolve raw source inputs through the service immediately before use.
Stale presentation, session or source evidence yields typed revalidation rather than a pass.

The narrow reviewer-separation credential is real separation, but it does not generalize to
proposer/approver/executor/reviewer lineage. No DS9 authority owner computes body composition,
forum, quorum, co-signature, conflict or recusal state, amount authority, succession or
subdelegation.

**Verdict: sound but incomplete.**

### 2.6 What DS20 actually encodes

The DS20 closure recorded a historical floor of **29 unsafe operations: 29 POST, zero PUT, zero
PATCH and zero DELETE**, each with one exact server-owned action permission and pre-policy resource
binding; its closure also recorded 29/29 denial/admission witnesses and six high-stakes operations
under five then-current step-up classes.

At the pinned post-DS9 baseline, the exact Python `RuntimePermission` enum and canonical Rego
`permission_vocabulary` each contain **34 values**. They agree exactly. The additional
`runs.human_decisions.create` value explains why the older DS20 closure prose says 33. That is
documentation drift in a historical closure record, not a permission-parity failure.

The current enforcement vocabulary can express:

- verified principal subject, tenant and effective identity;
- exact runtime role-derived permission;
- exact operation;
- exact resource class and digest;
- one of five binding-authority classes:
  `candidate`, `content_resolved_unscoped`, `ownership_verified`, `request_bound`,
  `tenant_collection`;
- one of two authorization sources:
  `canonical_role_permissions`, `deployment_service_principal`;
- fresh, signed, request-bound MFA step-up with replay protection.

It cannot express an office appointment, delegation provenance, a collegial body's constitution,
jurisdictional competence, amount authority, conflict posture or legal effect. Treating its `allow`
as proof of those facts would be a category error the DS20 design itself does not make.

**Verdict: sound within its runtime-authorization boundary; incomplete for institutional decision
authority.**

### 2.7 Landed acquisition-approval composition

The acquisition HTTP operation is `ingest_data`. Its route declares
`RuntimePermission.EVIDENCE_ACQUIRE`, a request-bound `runtime.evidence.acquisition` resource and
`StepUpClass.ACQUISITION_APPROVAL`. The current `StepUpClass` owner contains six classes: promotion,
production approval, publication, revocation, acquisition approval and human decision.

The repository does not contain one separately named acquisition-specific
`DecisionAuthorityGraph` or `DelegationValidityCertificate`. The landed behavior is a composition:

1. DS20 binds the acquisition operation, resource and principal and requires fresh step-up.
2. GY-PA2 supplies the mandate-bounded operational authority arm.
3. DS9's gateway adapter re-resolves that arm from raw signed inputs rather than trusting a
   serialized gate result.
4. DS9 currentness and guarded-store logic reject expired or revoked authority before protected
   consumption and prevent an unguarded record write.

This is the closest shipped seam to a pre-action certificate. It is still a revalidated operational
permission decision, not the full institutional authority proof specified here.

**Verdict: sound but incomplete.**

### 2.8 Attribute-by-attribute repository capability

`represented` means the shipped canonical chain can carry and enforce the required semantic.
`partial` means it enforces a narrower predicate but cannot represent the whole required attribute.
`not representable` means no field, producer and consumer in the strict canonical chain can carry
the semantic.

| Required attribute | Today | Repository coordinate | Exact missing part |
| --- | --- | --- | --- |
| 1. Temporal and subject-matter delegation | **partial** | `DelegatedActionEnvelope`; GY-PA2 five-predicate decision and accountability check | No source-law/jurisdiction power, amount/valuation, reserved matter or legal-purpose scope. |
| 2. Quorum and co-signature | **not representable** | `DecisionRole.GOVERNANCE_BOARD` is only a role token; no body/session/threshold owner in the 10-file chain | No forum identity, roster, eligible-member timeline, denominator, vote branches, quorum rule or counter-signature requirement. |
| 3. Separation of duties | **partial** | `ReviewerSeparationCredential` binds reviewer to exact reviewed actor(s) and change actions | No general proposer→approver→executor→independent-review transaction lineage or controlling-subject resolution. |
| 4. Recusal and conflict of interest | **not representable** | No conflict/recusal field or predicate in the strict delegation, PA2, DS9, DS20 or Rego owners | No disclosure, detected conflict, recusal, waiver, management measure or detectability boundary. |
| 5. Acting appointments and succession | **not representable** | Principal binding resolves a current subject/role but carries no appointment provenance | No office vacancy, acting basis, succession order, qualification, nomination restriction or predecessor chain. |
| 6. Subdelegation limits | **not representable** | Envelope has no parent grant or delegation-right field | No `may_subdelegate`, depth, permitted delegee class, child-scope intersection or creation-time authority check. |
| 7. Expiry and emergency authority | **partial** | Envelope `valid_from`/`valid_until`/`active|revoked`; GY-PA2/DS9 currentness | No emergency source, trigger, necessity/urgency determination, exceptional scope or emergency expiry profile. |
| 8. Revocation mid-operation | **partial** | Source/currentness is re-resolved before protected DS9 consumption; revoked/expired envelopes refuse | No checkpoint algebra for a long operation, dependency-aware cancellation, irreversible-effect rule or rollback/incident consequence. |
| 9. Cross-agency acceptance | **not representable** | DS9 producer trust authenticates a manifest/signer, not a legal recognition rule | No `recognised_as`/negative perimeter, legal gateway, refusal grounds, retained local duties or responsibility allocation. |
| 10. Consultation/recommendation/approval/binding decision | **not representable** | Existing workflow actions and source kinds do not encode legal effect | No formal type plus binding effect, condition precedent, freedom to depart, operative act or ultimate decision-maker. |

Cross-cutting coordinates from the question:

| Coordinate | Today |
| --- | --- |
| specific person and runtime role | represented |
| exact runtime operation and resource | represented |
| time window/currentness | represented narrowly |
| jurisdictional competence | not representable |
| amount threshold, currency, aggregation and valuation basis | not representable |
| conflict-of-interest posture | not representable |
| collegial-body validity | not representable |

### 2.9 Current capability label and reuse-first path

The full INT-R5 capability is **`absent/unallocated`**, not `contract_only`: no
`DecisionAuthorityGraph`, no `DelegationValidityCertificate`, no appointed institutional owner, no
complete producer chain and no consumer enforcing such a certificate exist. This research prose
does not change that label.

The smallest visible reuse-first path is:

1. extend the existing mandate/delegation owner rather than create a parallel permission system;
2. make DS9's pre-effect gateway the certificate consumer and revalidation chokepoint;
3. project certificate-required action/resource facts into DS20's existing permission/resource
   input without teaching DS20 legal competence;
4. reuse existing CAS, signature, event, reservation, audit and step-up machinery;
5. add purpose-specific external evidence adapters for institutional facts;
6. keep Atlas as projection only, with DS14 as a later consumer;
7. keep `PAO-R4` as an independent gate.

No canonical implementation owner is appointed by this research.

## 3. External Research Baseline

## 4. Result

## 5. Counterexamples And Failure Modes

## 6. Benchmark Or Fixture Proposal

## 7. Artifact Contract Sketch

## 8. Later Integration Handoff

## 9. Promotion And Kill Rules

## 10. Open Questions For Consolidation
