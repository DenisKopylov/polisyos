# INT-R5 Seam And Crosscheck

## 1. Scope And Method

This crosscheck asks a narrower question than the formal audit:

> Do the components the package names actually connect to each other on the protected production
> effect, and does each transition preserve rather than manufacture authority?

The method follows the executable path from HTTP dependency through route handler, service method,
authority resolver, persistence boundary and downstream effect. Adjacency, shared vocabulary and
reuse suitability do not count as a live seam.

The checked subjects are:

- GY-PA2 operational authority;
- DS9 human-decision custody/currentness;
- DS20 action permission, resource binding and step-up;
- `POST /api/v1/control/data/ingest`;
- PAO-R4 individual-use boundary;
- the five external surveys as inputs to the target model.

## 2. GY-PA2 Crosscheck

### 2.1 Positive path

The PA2 decision owns the following bounded conjunction:

```text
verified_identity
∩ explicit_permission
∩ mandate_bounded_delegation
∩ operation_in_envelope
∩ live_accountability
```

The path binds:

- exact operation/action identity;
- invocation and intent identity;
- subject and tenant;
- runtime roles and required permission;
- resource and contract digest;
- envelope `valid_from`, `valid_until` and `active|revoked` status;
- decision request and source references.

### 2.2 Negative path

The inspected resolver refuses:

- missing or ambiguous delegation;
- subject/tenant/resource mismatch;
- operation outside envelope;
- role mismatch;
- not-yet-valid, expired or revoked envelope;
- untrusted or unreconciled authority evidence.

No false-positive branch was found inside that declared predicate set.

### 2.3 Boundary

PA2 does **not** establish:

- source-law power;
- amount/valuation/anti-splitting;
- office appointment, succession or subdelegation provenance;
- forum, quorum or co-signature;
- COI/recusal;
- recognition or legal effect.

The package's narrow PA2 verdict survives.

## 3. DS9 Crosscheck

### 3.1 Route separation

The human-decision route exposes run-bound endpoints under `/api/v1/runs`. Its create mutation has its
own exact permission, run resource binding and `HUMAN_DECISION` step-up. Caller-authored input is
strict and forbids custody fields.

The route's source union distinguishes:

```text
agent_action_authority
production_approval
```

A PA2 source requires exact `source_ref` and `action_kind`; a production source cannot carry a PA2
action kind.

### 3.2 Service behavior

DS9 re-resolves the selected source from raw content-addressed inputs. It does not accept a serialized
“gate passed” Boolean as authority. The service binds:

- principal/key/role/permission validity;
- reviewer-separation credential;
- decision request and evidence exposure;
- presentation contract and verifier epoch;
- source currentness;
- reservation generation, CAS identity, signature and event evidence;
- guarded write, readback and recovery state.

### 3.3 Supported seam claim

DS9 is an appropriate **future consumer** for a delegation-validity certificate because it already
owns pre-use source resolution, currentness and guarded custody. This is a reuse/placement claim, not
a claim that DS9 currently understands institutional authority.

### 3.4 Unsupported extension

Nothing in DS9 automatically attaches it to every DS20 high-stakes route. A route must depend on or
invoke the DS9 gate/service explicitly. That edge is absent on acquisition.

## 4. DS20 Crosscheck

### 4.1 Runtime permission floor

DS20 provides the narrow floor the package describes:

```text
verified runtime principal
+ exact RuntimePermission
+ exact operation
+ exact resource class/digest
+ authorization source/binding authority
+ signed request-bound step-up
+ replay protection
```

The 34 Python enum members and 34 Rego vocabulary entries agree exactly at the pin. The historical
closure's 33-value text predates `runs.human_decisions.create`; this is documentation drift, not a
runtime parity defect.

### 4.2 Authority boundary

DS20's `allow` does not claim office, delegation provenance, quorum, conflict state or legal effect.
The package correctly resists treating authentication/authorization as institutional competence.

### 4.3 Required composition rule

For INT-R5, DS20 can be the final operation/resource enforcement floor only after an upstream
certificate/currentness consumer has actually bound the exact effect. Merely assigning a high-stakes
step-up class does not establish that upstream institutional predicate.

## 5. Acquisition-Gateway Crosscheck

### 5.1 Actual production path

The route is:

```text
POST /api/v1/control/data/ingest
```

Its declared dependencies are exactly:

```text
_INGEST_DATA_AUTHZ
  RuntimePermission.EVIDENCE_ACQUIRE
  ResourceBindingSource.REQUEST_COMPOSITE
  resource_kind = runtime.evidence.acquisition
  selectors = binding profile / connection profile / datasets / fetch plans

_INGEST_DATA_STEP_UP
  StepUpClass.ACQUISITION_APPROVAL
```

The route handler then calls:

```text
ControlPlaneService.run_data_ingestion(body, request_id)
```

The service:

1. converts datasets/fetch plans into connector fetch specs;
2. resolves an optional connection profile;
3. constructs ingestion dependencies;
4. dispatches replay, record, streaming, incremental or orchestrated ingestion;
5. optionally produces input bindings;
6. returns an ingestion result.

### 5.2 Missing edges

The route/service path has no:

- `HumanDecisionPA2GateInput`;
- PA2 source resolver;
- `HumanDecisionService` call;
- human-decision record reference;
- reviewer-separation receipt;
- decision presentation/exposure receipt;
- guarded human-decision write/readback;
- pre-effect institutional currentness check.

The general DS9 PA2 arm exists on the separate human-decision route. It is not consumed here.

### 5.3 Package contradiction

The package says acquisition is a landed composition in which:

1. DS20 binds acquisition;
2. GY-PA2 supplies mandate authority;
3. DS9 re-resolves the PA2 arm;
4. DS9 currentness and guarded-store logic protect use.

Only item 1 is present on the production acquisition route. Items 2–4 describe reusable components
that are not connected to the effect.

### 5.4 Correct standing

The accurate standing is:

```yaml
DS20 acquisition operation floor: implemented
PA2 authority producer: implemented for its own gateway contract
DS9 PA2/currentness/custody seam: implemented for run-bound human decisions
acquisition -> PA2/DS9 bridge: missing
acquisition institutional authority consumer: missing
full INT-R5 capability: absent/unallocated
```

This is `INT-R5-A-002`, **material**. It also establishes one real instance under T2 where
“incomplete” absorbed a wrong topology claim.

## 6. PAO-R4 Crosscheck

### 6.1 What PAO-R4 governs

PAO-R4 governs a different transition:

```text
policy-level or empirical artifact
    -> named governed case-system boundary
    -> protected individual action
```

It controls semantic class, denied uses, observable consultation, consumer gate and complete
returning evidence. It does not determine external office competence or make the individual act.

### 6.2 INT-R5 conceptual separation

INT-R5 correctly states:

```text
valid authority certificate != PAO-R4 pass
PAO-R4 pass != decision-maker authority
```

The graph/certificate `may_not_use_for` clause explicitly denies individual-case authorization.
There is no conceptual absorption.

### 6.3 Missing executable conjunction

The target `EffectAuthority` formula and handoff omit the conditional case crossing. The future
consumer sequence is written as:

```text
DecisionAuthorityGraph
-> DelegationValidityCertificate
-> DS9/currentness
-> DS20-protected effect
```

For an individual-case effect it must be:

```text
DecisionAuthorityGraph
-> DelegationValidityCertificate
-> DS9/currentness
-> PAO-R4 crossing-gate receipt
-> DS20-protected effect
```

or another order proven equivalent without allowing either gate to infer the other.

A `may_not_use_for` annotation helps projection and review; it does not force a runtime consumer to
obtain the missing receipt.

This is `INT-R5-A-007`, **material**.

## 7. External-Survey Crosscheck

### 7.1 Delegation survey

The package faithfully transfers the survey's main constraints:

- role alone is insufficient;
- scope includes subject, time, amount, place, trigger and reserved matters;
- acting/succession and implied authorization are distinct edges;
- subdelegation requires creation-time power and attenuation;
- emergency is a conditional source, not permanent elevation;
- revocation uses legal-effective time, not only actor notice;
- cure consequences differ by regime.

The package also preserves the survey's warning that a general ban on post-hoc cure is false.

### 7.2 Collegial survey

The package correctly preserves:

- organ/forum identity apart from participant identity;
- composition and appointment provenance;
- profile-specific presence and quorum denominator;
- item-level event timeline;
- separate vote and co-signature predicates;
- evidentiary record distinct from constitutive validity;
- profile-specific void/voidable/saved/curable consequences.

The three quorum temporal profiles in the fixture are a strong transfer, not a universalization.

### 7.3 COI/recusal survey

The package correctly transfers:

- structural self-approval versus manageable COI;
- controlling subject rather than username;
- transaction-level proposer/contributor/approver/executor/reviewer lineage;
- meta-self-approval hazard;
- record-established, record-indicated, self-known and evaluative conflict classes;
- bounded positive language rather than “no conflict exists”.

No T7 violation was found.

### 7.4 Pre-action/freshness survey

The package correctly transfers:

- proof rather than decision receipt;
- chain/path reduction;
- exact action commitment;
- freshness horizon as evidence bound rather than no-revocation guarantee;
- snapshot/lease/revalidation distinction;
- dependency-aware mid-operation reaction;
- no fictional rollback after irreversible effect.

It incorrectly copies the survey's illustrative `!=` expression into a theorem-like universal. The
survey's prose supports non-inferability, not actual inequality in every history. This is A-001.

### 7.5 Cross-agency/act-type survey

The package correctly transfers:

- acceptance of a specific assertion under a legal/trust gateway;
- `recognised_as` plus negative perimeter;
- retained local duties and responsibility allocation;
- distinction between authenticity, truth, recognition, authorization and final decision;
- act classification by legal effect rather than title;
- formal binding effect apart from practical departure cost.

No universal recognition rule was found.

### 7.6 Evidence-custody limitation

Although the semantic transfers are mostly faithful, the package branch does not preserve exact
survey identities or anchors. This crosscheck depended on session-supplied files outside the branch.
That is A-005 and prevents branch-only independent replay.

## 8. Seam Verdict

| Seam | Verdict |
|---|---|
| GY-PA2 internal predicate seam | **holds within declared scope** |
| DS9 PA2/production source and currentness seam | **holds on run-bound human-decision routes** |
| DS20 permission/resource/step-up seam | **holds** |
| DS20 acquisition -> PA2/DS9 institutional authority seam | **does not exist** |
| INT-R5 conceptual boundary -> PAO-R4 | **holds** |
| INT-R5 effect consumer -> PAO-R4 for individual case | **missing** |
| five survey semantics -> target model | **mostly holds** |
| five survey evidence -> branch-replayable custody | **does not hold** |

The seam evidence supports `GO_WITH_REVISIONS`: the reusable components are real, but two load-bearing
compositions — acquisition authority and individual-case crossing — are narrated rather than wired.
