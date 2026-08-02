---
title: PAO-R1 Recommended Research Revision
status: draft_audit
kind: research-audit
research_task: PAO-R1
source_report_status: delivered
source_report_result_type: accepted_narrow_scope
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
pao_r0_audit_commit: 258aa740efcfb9e6771bfe52d4fdabc6b74f93a7
audit_date: 2026-07-26
audit_branch: research/pao-r1-independent-audit
authoritative_for:
  - repository audit findings at the recorded commits
  - recommended corrections to the PAO-R1 research artifact
may_not_use_for:
  - production capability claim
  - legal or institutional authority allocation
  - final code contract
  - production implementation authorization
  - automatic boundary adjudication
  - direct modification of authoritative plans
  - proof that an external institution performed a function
research_only: true
---

# PAO-R1 — Operational Boundary Method and Candidate Evidence-Interface Register

> Proposed corrected research artifact. It does not overwrite the delivered
> report and is not a ratified plan, owner decision, runtime contract, legal
> allocation, or implementation authorization.

## Executive Finding

**Proposed result: `accepted_narrower_scope`.**

The ratified four-way custody test is a strong basis for boundary review. The
delivered research also identifies a valuable decomposition:

```text
external act
→ external evidence emission
→ PolicyOS receipt/verification/admission
→ PolicyOS claim reaction
→ public projection
```

These planes must not be collapsed into one verdict or ownership field.

For an external act whose result can change a PolicyOS claim:

- the act remains externally owned and PolicyOS execution is prohibited;
- the evidence relationship is `INTEGRATE`;
- purpose-specific verification/admission is PolicyOS-owned;
- the affected canonical claim owner owns reaction;
- the publication owner emits an authoritative projection and Atlas renders it
  without minting authority.

The full 213-row register and 21 `EC-*` catalogue are candidate research
hypotheses. They are not ready to constrain all Wave-2 tasks. A smaller packet
of ratified invariants and safe research guidance can be used during
consolidation.

## 1. Task and project fit

PAO-R1 applies, but does not reopen, the
[ratified identity decision](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md#L88-L139).
It produces:

1. a research method for decomposing functions;
2. a candidate question set for institutional pilots;
3. a disposition ledger for candidate rows and evidence families;
4. semantic fixture proposals for OPS-R15.

It does not create a global runtime register, assign external legal authority,
ratify owners, or reclassify backlog tasks.

PAO-R0 is an external dependency only for future subject references. The
unmerged PAO-R0 audit found PolicyMatter ownership, namespace and contract shape
unsettled. `policy_matter_ref` therefore remains optional and
`requires_pao_r0_consolidation`.

## 2. Repository baseline

Historical and current repository baselines are identical:

```text
4813b49f6ce14e8debf3aaea096f0967d38d9768
```

There are no current-main staleness findings. Confirmed repository facts:

- the four-way test and anti-roles are ratified;
- PDC has a purpose-scoped `AuthorityBoundary`;
- runtime quality and Fabric contain overlapping admission/source envelopes;
- Lex and Data Forge split runtime legal evaluation from offline corpus
  production;
- ADR-0170 separates appeal administration from outcome ingestion;
- decision validity and continuous governance contain scoped lifecycle
  primitives;
- core audit owns portable verification packages, not external audit opinions;
- runtime authorization records admission, not handler success;
- Atlas is intended to render authority, although the active plan documents
  known surface-minting defects;
- no implemented `OperationalBoundaryDecision`,
  `InstitutionalEvidenceEnvelope`, generic proof-of-service contract,
  `policy_matter_ref`, or BND fixture exists.

Capability labels must be assigned per chain. Existing local contracts do not
prove a complete generic institutional-evidence capability.

## 3. External research baseline

External sources support role separation, provenance, service ownership,
qualified-delivery distinctions, independent audit roles, records duties and
institutional procurement governance within their respective scopes. They do
not establish a universal cross-jurisdiction owner map or PolicyOS schema.

Use final/canonical sources:

- [W3C PROV-O Recommendation](https://www.w3.org/TR/prov-o/), not the 2012
  working draft;
- [GAO 2025 Green Book](https://www.gao.gov/assets/890/882014.pdf), not a
  corrupted-label press-release citation;
- [OECD Governing with Artificial Intelligence](https://www.oecd.org/en/publications/governing-with-artificial-intelligence_795de142-en/full-report.html),
  not its press release.

EU, UK and US legal/administrative sources are examples within jurisdiction.
Operator identity, legal effect, competence, retention and finality remain
`external_verification_required`, `jurisdiction_dependent` and often
`pilot_dependent`.

## 4. Corrected result

### 4.1 Unit of analysis

The review method asks:

```text
narrow act
× affected PolicyOS claim/dependency
× jurisdiction/time-scoped operator assertion
× evidence crossing
× admission decision
× consumer reaction
× projection
```

These are linked objects, not necessarily one stored row. One artifact can
affect multiple claims; one operator can perform multiple roles; one function
can have different operators across jurisdictions and time.

### 4.2 Corrected four-way operationalization

| Plane | Correct classification |
| --- | --- |
| PolicyOS epistemic/custody act required to keep its claim honest | `OWN` |
| External institutional act | External owner; PolicyOS execution prohibited |
| External result that can alter PolicyOS claim validity/scope | Evidence relationship `INTEGRATE` |
| Context/risk signal with no current claim effect | `OBSERVE`; new admitted artifact required for authority |
| Act with no legitimate claim/evidence role or an anti-role | `OUT_OF_SCOPE` |
| Verification/admission of external evidence | `OWN`, by the actual canonical admission owner |
| Scoped claim reaction | `OWN`, by the actual canonical claim owner |
| Projection | PolicyOS publication discipline; renderer cannot mint authority |

### 4.3 Corrected role model

Record roles only when supported:

- `external_act_operator`;
- `evidence_issuer`;
- `source_contract_owner`;
- `admission_verifier`;
- `claim_dependency_owner`;
- `reaction_executor`;
- `publication_owner`;
- `projection_renderer`;
- `institutional_review_forum`, where applicable.

Do not use an `owner_state` that mixes external competence with implementation
completeness. Record capability-chain state separately.

### 4.4 Absence and reaction

Safe invariant:

> Missing, late, stale, contradictory or revoked evidence is not evidence that
> the external act did not occur.

The evidence/source record may state the condition and admission disposition.
The canonical consumer decides claim-specific materiality and reaction.
`block`, `freeze`, `recompute`, `reissue`, `withdraw`, or indefinite
preservation cannot be universal defaults.

### 4.5 Observation

An observation may trigger acquisition or human review. That trigger does not
make the observation evidence. Authority changes only through a new
purpose-bound admission receipt and canonical claim transition.

### 4.6 Capability reality

For each proposed integration prove:

```text
family-native typed contract
→ real producer
→ persisted artifact/event
→ bridge
→ purpose-specific verifier/admission
→ actual claim consumer/reaction
→ surface or explicit exclusion
→ semantic negative test
```

Use repository capability labels exactly. A plan, DTO, fixture or type is not a
complete capability.

### 4.7 Register disposition summary

The detailed row audit is external to this proposed revision. At the family
level:

| Family | Standing |
| --- | --- |
| PolicyOS grounding/admission/signing/revalidation/correction/replay/internal authorization | High-confidence OWN, subject to actual capability labels |
| Legal sensing | Split Data Forge source production, Lex evaluation, external enactment/adjudication and claim reaction |
| Appeals/incidents | External act + INTEGRATE outcome/report + OWN admission/reaction |
| Administrative procedure/notices/payments/service/procurement/records | External act owner unresolved; pilot/jurisdiction evidence interface only |
| Monitoring/learning | Split external observation, PolicyOS admission/diagnosis and separately gated model/policy reaction |
| Public projection | Publication owners distributed; Atlas renders only |
| PolicyMatter | Unresolved PAO-R0 dependency |
| H2 | Future consumer/orchestrator, not a current owner |

All external-act rows require the plane split. Duplicate appeal, remedy,
procurement, incident, payment, hold, correction, audit and continuity rows
should be normalized into linked objects.

## 5. Counterexamples and failure modes

Preserve these falsifiers:

- receiving an appeal outcome does not mean PolicyOS adjudicated;
- authorization is not execution, settlement or reconciliation;
- “sent” is not legally served;
- a service dashboard is not delivery proof;
- a core audit package is not an independent audit opinion;
- a signature proves integrity only within its verified subject, purpose,
  competence and jurisdiction;
- a DDM/media/risk signal is not admitted incident authority;
- external outage means unknown/stale, not non-occurrence;
- boundary and evidence corrections append/supersede; they do not rewrite
  history;
- technical saga `compensation` must never surface as financial/public remedy;
- H2/custody workers must hard-fail external payment, notice, case-management,
  procurement and service execution.

Correct failure-pattern references using the canonical register. `M31` is a
distillation move, not a failure pattern. Use P13 only for contract gravity,
not as a generic synonym for institutional scope inflation.

## 6. Benchmark or fixture proposal

The BND catalogue remains `planned_not_implemented`. Preserve the scenarios but:

- correct pattern references;
- split every external act from evidence/admission/reaction;
- bind fixtures to actual claim/dependency IDs;
- include jurisdiction and pilot assumptions;
- test the real intake/emission path, not marker presence;
- require the verifier itself to fail on a corrupted decisive field;
- distinguish integrity, identity, competence, scope, finality, semantic
  adequacy and claim-specific admission.

Recommended zero sentinels for OPS-R15 remain proposals:

```text
out_of_boundary_actions_attempted = 0
external_execution_overclaims = 0
observation_authority_upgrades = 0
missing_claim_critical_routes = 0
silent_historical_rewrites = 0
```

Do not freeze a corpus size until the normalized row model and adjudication
procedure are independently reviewed.

## 7. Research-only contract sketches

Every shape in this section is:

```text
research_only: true
candidate_for_consolidation: true
```

### 7.1 Candidate boundary review record

This is a reviewer worksheet, not a runtime contract:

```yaml
boundary_review:
  narrow_act_definition: ...
  affected_claim_or_dependency_refs: [...]
  external_operator_assertions:
    - institution_ref: ...
      jurisdiction_scope: ...
      effective_interval: ...
      competence_evidence_refs: [...]
      grounding_status: grounded | provisional | unresolved
  evidence_family_ref: ...
  canonical_source_contract_owner: ...
  canonical_admission_owner: ...
  canonical_claim_owner: ...
  publication_owner: ...
  projection_renderer: ...
  capability_chain_state: ...
  absence_questions: [...]
  prohibited_execution_claim: ...
  open_questions: [...]
  confidence: high | medium | low
```

No common boundary-decision workflow statuses are proposed.

### 7.2 Candidate admission receipt composition

Do not create an `InstitutionalEvidenceEnvelope`. Compose:

```yaml
family_native_evidence_ref: ...
provenance_graph_ref: ...
source_contract_ref: ...
authority_boundary_ref: ...
temporal_roles_ref: ...  # owned by OPS-R4
admission_receipt:
  verifier_ref: ...
  rule_version_ref: ...
  integrity_result: ...
  source_identity_result: ...
  competence_result: ...
  subject_scope_result: ...
  jurisdiction_result: ...
  freshness_result: ...
  admitted_for: [...]
  may_not_use_for: [...]
  audit_event_ref: ...
consumer_impact_ref: ...  # separately owned
```

`policy_matter_ref` may appear only as an optional adapter-level external
dependency after PAO-R0 consolidation.

### 7.3 Evidence-family catalogue

`EC-01`–`EC-21` are a research mapping catalogue. They must be split, composed
or deferred according to the evidence-contract audit; none is a canonical code
contract.

## 8. Later integration handoff

| Consumer | Safe handoff |
| --- | --- |
| PAO-R0 | Resolve subject identity/namespace/owner before common matter refs |
| OPS-R4 | Define shared temporal roles and late/correction semantics |
| OPS-R5 | Define observation/KPI/diagnosis/adaptation boundaries |
| OPS-R10 | Consolidate Data Forge, Lex and legal-world bridges |
| INT-R5 | Own competence/delegation/pre-action authority research |
| INT-R7 | Own public proof/key/archive lifecycle |
| PAO-R36 | Own correction of PolicyOS public records and cache/feed fan-out |
| OPS-R15 | Execute normalized semantic corpus and zero-sentinel capstone |
| Atlas | Render authoritative projections only |
| Future H2 | Orchestrate waits/revalidation only after anti-role hard blocks |

Deferred-task entries remain advisory reviews. PAO-R1 does not reclassify them.
Active OPS-R14 and PAO-R36 are overlap notes, not deferred tasks.

## 9. Promotion and kill rules

### 9.1 Current standing

`research_only`.

### 9.2 Prototype guidance

Synthetic reviewer tools and fixtures are permissible only with non-authoritative
data, explicit candidate labels, no external act execution, no production
status changes and no parallel canonical owner.

### 9.3 Consolidation prerequisites

- actual canonical-owner review;
- PAO-R0 and OPS-R4 resolution;
- jurisdiction/pilot operator evidence;
- complete capability chains;
- semantic negative tests;
- tenant/jurisdiction isolation;
- append-only correction/replay;
- public wording tests;
- explicit human-principal/architecture acceptance.

### 9.4 Kill rules

Reject a proposal that:

- performs a ratified anti-role;
- treats evidence receipt as execution;
- treats observation, projection, integrity or signature alone as authority;
- lets missing claim-critical evidence become a pass;
- lets an external producer prescribe PolicyOS claim reaction;
- duplicates a canonical owner or creates another status lattice;
- silently rewrites a boundary/evidence/claim history;
- universalizes a jurisdiction-specific legal rule;
- calls a contract/type/fixture a complete capability.

## 10. Open questions for consolidation

1. Should a global boundary-review artifact exist at all, or should boundary
   decisions remain domain-owned linked assertions?
2. Which human/institutional principal can ratify a cross-institution row?
3. How will OPS-R4 distinguish family clocks from receipt/admission/audit time?
4. Which existing authority-boundary types should be referenced, composed or
   consolidated?
5. What is the canonical admission receipt owner for each family?
6. How are competence/finality conflicts between external bodies represented?
7. Which absence conditions materially block which actual claims?
8. How are tenant and jurisdiction trust federated?
9. Which public owner—not merely renderer—may state external execution status?
10. How will boundary changes bind to real dependency keys and preserve replay?

### Proposed Stage-0 guidance by standing

| Guidance | Standing |
| --- | --- |
| PolicyOS owns what it signs and must keep its claims honest | Ratified invariant |
| PolicyOS must not perform the ratified anti-roles | Ratified invariant |
| External act ownership, evidence integration and PolicyOS reaction are distinct | Ratified invariant clarified by safe research guidance |
| Observation/projection cannot mint authority | Ratified invariant |
| Missing claim-critical evidence cannot be treated as non-occurrence or a pass | Ratified fail-closed invariant |
| Reuse existing canonical owners and one-lattice composition | Ratified/repository invariant |
| Exact ownership fields, evidence envelope, statuses, clocks and challenge workflow | Proposed architecture; not frozen |
| Complete 213-row verdict register | Research hypotheses; not frozen |
| Deferred-task reclassifications | Advisory only |
| Quarterly review and mass-impact workflow | Governance proposal requiring acceptance |

### Final research posture

The method, anti-role boundary, act/evidence distinction, responsibility for
PolicyOS claim reaction, observation firewall, package/opinion distinction,
unknown-on-absence invariant and semantic fixtures are strong. The complete
register, universal envelope, owner map, status systems, clock set and Stage-0
authority claim must remain open for consolidation.
