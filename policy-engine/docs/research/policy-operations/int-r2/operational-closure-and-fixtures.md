---
title: INT-R2 — Operational Closure And Fixture Ledger
status: research_only
research_task: INT-R2
repository_commit: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
authoritative_for:
  - candidate process-state semantics for later implementation planning
  - candidate semantic fixture denominator and acceptance measures
may_not_use_for:
  - runtime status-lattice creation
  - production authority
  - institutional signer simulation
  - capability claim
---

# INT-R2 — Operational Closure And Fixture Ledger

## 1. State-machine boundary

The states below are acquisition-process states, not a second Atlas authority/readiness lattice. Each
state emits or references the existing status-lattice input owned by the demanding gate. No transition
in this machine means `approved`, `publishable`, `governed` or `production`.

```text
UNCLASSIFIED_REFUSAL
  → SHAPE_ASSESSING
      → SHAPE_NOT_ESTABLISHED
      → CLASSIFIED
          → ROUTED
              → EVIDENCE_RECEIVED
                  → ADMISSION_REFUSED
                  → ADMITTED_REENTRY_REQUIRED
                      → REENTRY_CLOSED
                      → REENTRY_PROVISIONAL_REFUSAL
                      → DEEPER_TERMINAL

REENTRY_CLOSED | REENTRY_PROVISIONAL_REFUSAL | DEEPER_TERMINAL
  -- material trigger --> STALE_REVALIDATION_REQUIRED
  → SHAPE_ASSESSING or ADMITTED_REENTRY_REQUIRED
```

### 1.1 State semantics

| State | Entry evidence | Owner | Clock/expiry | Exit | Public meaning |
| --- | --- | --- | --- | --- | --- |
| `UNCLASSIFIED_REFUSAL` | Existing typed refusal/residual, no proved missing-object class. | Demanding gate owner. | Current gate/reference epoch. | Begin shape assessment. | Blocked; the system does not yet know what kind of acquisition could close it. |
| `SHAPE_ASSESSING` | Frozen residual, demanding predicate and evidence regime. | Future non-data acquisition classifier. | Assessment attempt/cutoff. | `SHAPE_NOT_ESTABLISHED` or `CLASSIFIED`. | Classification in progress; no data-default. |
| `SHAPE_NOT_ESTABLISHED` | Assessment cannot establish one or more case types with positive-eligible P37 predicates. | Classifier owner. | Reopen only on new classifier evidence/rule. | Back to assessment. | Blocked with a better-characterised unknown; not terminal and not a data request. |
| `CLASSIFIED` | `GapShapeAssessment` with `one_case` or `split_required`. | Classifier owner. | Bound to rule/version and demanded scope. | Route exact case(s). | The required acquisition object is known; it is not acquired. |
| `ROUTED` | Case identifies eligible producer requirement and artifact kind. | Acquisition planner/control plane. | Route TTL or external response deadline; expiry only creates a new refusal. | Evidence received or explicit route failure. | Waiting on a named producer/path; route presence is not closure. |
| `EVIDENCE_RECEIVED` | Resolvable candidate artifact and provenance. | Admission verifier. | Artifact valid/current intervals. | Admission refused or admitted for re-entry. | Candidate evidence received; not yet usable by the demanding gate. |
| `ADMISSION_REFUSED` | Resolve/content-bind/producer/currentness/ceiling check fails. | Admission verifier. | Reopen on corrected artifact or owner change. | Route/receive again. | Evidence rejected or quarantined; the original blocker remains. |
| `ADMITTED_REENTRY_REQUIRED` | Artifact admitted for an exact purpose and ceiling. | Demanding gate owner. | Immediate bounded re-entry; stale before use means no evaluation. | Closed, provisional refusal or deeper terminal. | The system may re-evaluate; it may not auto-close. |
| `REENTRY_CLOSED` | The demanding owner reruns and its blocked predicate now passes within the admitted ceiling. | Demanding gate owner. | Current only until a case-type trigger fires. | Stale/revalidate on trigger. | This acquisition requirement is closed for the exact scope; adjacent gates remain independent. |
| `REENTRY_PROVISIONAL_REFUSAL` | Gate reruns but missing/insufficient/ambiguous evidence remains and no deeper-terminal proof exists. | Demanding gate owner. | Route-specific retry/review trigger. | Reclassify, route or stale. | Still blocked; a known acquisition route may remain. |
| `DEEPER_TERMINAL` | All five deeper-terminal tests pass and a branch-specific terminal proof is admitted. | Demanding gate owner, relying on the competent producer/verifier. | Terminal only for the stated route/regime/horizon; external change can reopen. | Stale/revalidate on a named external trigger. | More is known and the refusal is stronger. It is not near approval. |
| `STALE_REVALIDATION_REQUIRED` | Material scope/time/authority/evidence/relationship/dependency event. | Custody/lifecycle owner. | Until required rebinding completes. | Shape assessment or owner re-entry. | Prior result is historical; no current reliance is permitted. |

### 1.2 Transition invariants

1. No state enters `REENTRY_CLOSED` from `ROUTED` or `EVIDENCE_RECEIVED`.
2. No external producer may mark its own case closed; the demanding canonical gate recomputes closure.
3. Duplicate trigger/event receipts are idempotent and do not create a second authority effect.
4. Late/stale events may be retained for history but cannot revive an expired artifact.
5. `DEEPER_TERMINAL` requires admitted new boundary knowledge; retries and timeouts stay provisional.
6. A closed or terminal state can become stale without rewriting its historical record.
7. Compound `split_required` cases close only when every ordered case required by the demanding gate
   has independently closed.
8. Unknown P37 predicate provenance cannot support `CLASSIFIED`, admission or closure.

## 2. Candidate typed artifacts

These are research sketches. They name the contracts a later implementation must consolidate with
existing owners; they do not create canonical runtime types.

### 2.1 `GapShapeAssessment`

```yaml
schema_version: string
assessment_id: string
residual_ref: string
demanding_gate_ref: string
blocked_predicate: string
minimal_missing_object: string | null
current_evidence_regime_ref: string
same_stream_data_effect: can_change | cannot_change | not_established
candidate_case_types: [GapAcquisitionCaseType]
ruled_out_case_types:
  - case_type: GapAcquisitionCaseType
    evidence_refs: [string]
predicate_provenance:
  label: recomputed | independently_reconciled | consumer_asserted |
         institutionally_supplied | not_established
  source_refs: [string]
classification_outcome: data_gap | one_case | split_required | not_established
ordered_case_types: [GapAcquisitionCaseType]
rule_version_ref: string
content_hash: string
```

### 2.2 `GapAcquisitionCase`

A discriminated union over the eight INT-R2 case types. The common envelope binds residual, demanding
gate, blocked claim/action, required object, producer requirement, sufficiency rule, admission proof,
authority ceiling, re-entry and terminal semantics. The branch owns the six substantive answers.

### 2.3 `AcquisitionArtifactEnvelope`

```yaml
artifact_id: string
artifact_kind: string
case_id: string
case_type: GapAcquisitionCaseType
producer_identity_ref: string
producer_standing_refs: [string]
subject_and_version_refs: [string]
source_evidence_refs: [string]
work_or_decision_record_refs: [string]
rule_and_procedure_refs: [string]
valid_time: object
transaction_time: object
content_hash: string
verifier_identity_ref: string
verification_method_ref: string
verification_time: timestamp
admission_disposition: admitted | degraded | quarantined | refused
admission_reasons: [string]
authority_ceiling: AuthorityCeiling
authoritative_for: [string]
may_not_use_for: [string]
```

Presence, shape, a self-declared verifier role or a valid signature cannot admit this envelope. The
verifier resolves, content-binds, proves non-producer provenance and re-resolves standing/currentness.

### 2.4 `AuthorityCeiling`

```yaml
claim_kinds: [registered_claim_kind]
action_refs: [string]
subject_refs: [string]
object_refs: [string]
population_scope_ref: string | null
jurisdiction_scope_ref: string | null
purpose_refs: [string]
audience_refs: [string]
source_context_ref: string | null
target_context_ref: string | null
valid_from: timestamp | null
valid_until: timestamp | null
review_at: timestamp | null
evidence_class_refs: [string]
maintained_assumption_refs: [string]
max_claim_strength_ref: string | null
max_commitment_stage_ref: string | null
permitted_operation_refs: [string]
prohibited_use_refs: [string]
required_downstream_gate_refs: [string]
source_rule_version_refs: [string]
reference_epoch_refs: [string]
```

A use is permitted only when every demanded dimension is established and the requested use is a
subset. Unknown fields fail closed; the consumer never silently narrows a broad request.

### 2.5 `GapAcquisitionReentryReceipt`

```yaml
receipt_id: string
case_id: string
trigger_event_ref: string
trigger_kind: registered_event_kind
trigger_targets_blocked_predicate: bool
prior_artifact_refs: [string]
new_artifact_refs: [string]
invalidated_fields: [string]
rebound_scope_refs: [string]
demanding_gate_ref: string
before_disposition: string
after_disposition: string
closure_recomputed: bool
automatic_closure_used: false
duplicate_or_replay_status: first_seen | idempotent_duplicate | historical_only
content_hash: string
```

### 2.6 `DeeperTerminalRecord`

```yaml
terminal_id: string
case_id: string
case_type: GapAcquisitionCaseType
prior_plausible_route_refs: [string]
new_admitted_evidence_refs: [string]
excluded_or_narrowed_routes: [string]
branch_terminal_kind_ref: string
terminal_scope: object
reentry_requires: [registered_event_kind]
not_authority_increase: true
not_near_success: true
reasoning_and_verifier_refs: [string]
content_hash: string
```

## 3. Canonical-owner map for later consolidation

| Concern | Existing owner to extend | Candidate disposition | Current gap |
| --- | --- | --- | --- |
| Gap demand/routing | `runtime/quality/acquisition_planner.py` | Extend the canonical planner boundary; do not build a second planner. | Generic non-data case family and producer registry absent. |
| Residual shape | No admitted owner | Candidate new function in the future knowledge/grounding acquisition plane. | `absent/unallocated`; stage 1 cannot appoint it. |
| Relation | CG0–CG3 grounding owners, causal evidence owners | Integrate a relation-acquisition artifact with the existing grounding gate. | No universal adjudicator/threshold or admitted producer chain. |
| Estimand | Existing method/grounding obligations and their canonical owners | Extend target/estimand evidence rather than infer from data schemas. | No canonical target-binding producer/artifact bridge. |
| Writability | Data overlay authority for its own source; external register owner for other systems | Reuse resolve-bind-verify and owner re-resolution; add operation-specific external contracts. | No generic truth/change-owner resolver. |
| Legal mandate | Lex competence/hierarchy owners | Extend Lex claim-level authority intake; do not create a parallel legal engine. | No appointed grantor and no complete action-level bridge. |
| Normative authorization | Participation/legal seeds; external regime owner | Integrate regime-specific determinations. | No generic producer registry; social-licence issuer often not established. |
| Capacity | No admitted end-to-end owner | Candidate runtime-quality evidence owner consuming direct delivery evidence and independent challenge. | `absent/unallocated`. |
| Competent decision | `runtime/quality/design_axes/mandate_bounded_delegation.py` and human-decision chain | Extend existing HumanDecisionRecord semantics. | Deployed competent producer pool and complete consumers absent. |
| Independent audit | `core/audit` packaging plus runtime assurance-case owners | Extend packaging/intake, not the external assurance institution. | Provider appointment and relationship/threat evidence absent. |
| Re-entry/custody | Existing lifecycle/epoch and demanding gate owners | Reuse event-triggered invalidation and exact-gate recomputation. | Multi-type bridges absent. |
| Surface | Atlas one-lattice projection | Render owner-produced process/status facts only. | Consumer waits; it cannot invent the union. |

## 4. Public regression fixture denominator

The proposed minimum **public regression denominator is 63 executable cases**, composed exactly as
follows:

| Family | Count | Measure |
| --- | ---: | --- |
| Eight direct happy-path acquisitions | 8 | One synthetic contract-test case per discriminator. |
| Eight trust-by-form adversaries | 8 | One per discriminator: plausible document/credential/signature/checklist that lacks a required producer/proof predicate. |
| Same-stream row-inflation metamorphics | 12 | Three protected types (`grounding_relation`, `estimand_binding`, `legal_mandate`) × four row counts `{0, 1, 1_000, 1_000_000}`. |
| Provisional-versus-deeper-terminal pairs | 16 | Eight discriminators × two states. |
| Re-entry cases | 8 | One per discriminator, including trigger targeting and no automatic closure. |
| Ceiling-escape cases | 8 | One attempted broader use per discriminator. |
| N13 capstone classification cases | 3 | `education`, `first_vertical`, `unseen`. |
| **Total** | **63** | `8 + 8 + 12 + 16 + 8 + 8 + 3`. |

The synthetic happy paths are `contract_testing` only. They may prove the contract’s behaviour; they
may not simulate or stand in for real institutional authority.

### 4.1 Required 8 trust-by-form adversaries

| Case type | Present form | Missing property | Required result |
| --- | --- | --- | --- |
| grounding relation | Expert DAG and citations | No governed integration/identification/claim-strength proof | Remain blocked; at most structured assumption. |
| estimand binding | Field named `estimand` | Missing one target attribute or identification mapping | Admission refused or semantic-only ceiling. |
| owner writability | Valid API token/ACL | No substantive change authority or operation right | Remain blocked. |
| legal mandate | Signed delegation memo | Issuer lacks competence/redelegation right | Remain blocked or deeper terminal if no competent grantor exists. |
| normative authorization | Consultation or popularity result | Governing regime requires consent/ethics determination | Remain blocked. |
| implementation capacity | Green checklist/composite score | One critical supplier/staff/load prerequisite is absent | No-go or narrower tranche; no averaging. |
| competent decision | Qualified person’s signature | No evidence of review/work or task lies outside scope | Decision not acquired. |
| independent audit | `external=true` report | Provider audited its own implementation or other unremedied threat | Independent audit not acquired. |

### 4.2 Same-stream row-inflation oracle

For each protected type, all four row-count fixtures carry identical missing-object and gate evidence.
The expected classification and closure result must be byte-equivalent after removing volatile
count/input-hash fields. A million rows may reduce estimation noise; it may not flip the non-data gate.

Negative control: a separate ordinary data-gap fixture must close when a valid admitted observation
changes the demanding owner’s availability predicate. This proves the harness can observe a legitimate
data closure rather than always refusing.

### 4.3 Deeper-terminal pairs

Each discriminator has two fixtures:

- **provisional:** missing/incomplete route, timeout, no response, or unresolved predicate;
- **deeper:** new admitted proof establishes the branch-specific boundary — for example
  non-identifiability, ill-defined estimand, invalid operation ontology, higher-order prohibition,
  competent disapproval, terminal-within-horizon capacity, no competent decision source, or no
  remediably independent provider.

The pair must differ in the admitted evidence and re-entry condition, never merely a label.

### 4.4 Re-entry and lifecycle cases

The eight re-entry fixtures jointly cover:

- a valid targeted trigger;
- a late event retained as history only;
- an idempotent duplicate;
- a conflicting authority event requiring fail-closed reconciliation;
- an unavailable owner/provider;
- a malicious or forged producer identity;
- a degraded/limited artifact that cannot satisfy a stronger gate; and
- historical replay under the old rule plus current revalidation under the new rule.

No fixture may transition from event receipt directly to closed/approved. Every closure is recomputed
by the demanding gate.

### 4.5 Capstone fixtures

- `education` must classify as `estimand_binding`, never `data_gap` merely because datasets are
  available.
- `first_vertical` and `unseen` must remain `split_required` or `not_established` until the fixture
  supplies evidence distinguishing relation absence from owner-writability absence.
- Adding rows to either disjunctive case must not pick a branch.

## 5. Sealed holdout

A later evaluation should add **16 sealed near-variants**, two per discriminator. Variants should
change surface form while preserving the property: synonymous document titles, valid-looking but
cross-bound identifiers, partial scope overlap, issuer succession, present-but-stale status,
independence through another network member, capacity evidence from a non-representative pilot and
other sibling-consumer paths.

The sealed pack is for falsification, not a new authority source. Only typed aggregate results escape;
answers and discriminator keys remain sealed.

## 6. Measures and acceptance signal

| Measure | Denominator | Required public-regression result |
| --- | ---: | ---: |
| Happy-path closure | 8 | 8/8 close only after admitted proof and demanding-gate re-entry. |
| Trust-by-form false close | 8 | 0/8. |
| Protected row-inflation false close | 12 | 0/12. |
| Provisional/deeper discrimination | 16 | 16/16 match the evidence-defined member of each pair. |
| Re-entry automatic closure | 8 | 0/8. |
| Ceiling escape | 8 | 0/8. |
| Capstone data-default or false single type | 3 | 0/3. |
| Overall unsafe false close/ceiling escape | 63 | 0/63. |

Additional diagnostics: false terminal, false merge, unclassified-to-data default, duplicate-event
authority multiplication and replay drift. Structural/schema checks alone cannot satisfy the benchmark;
the tests must run the real classifier, admission, ceiling and re-entry properties.

## 7. Edge-case addendum coverage

| Required Group-A edge class | Fixture coverage |
| --- | --- |
| happy path | Eight direct acquisitions. |
| missing evidence | Eight trust-by-form adversaries. |
| late event | Re-entry late-event case. |
| duplicate event | Re-entry idempotency case. |
| conflicting authority | Legal/normative/writability reconciliation case. |
| owner unavailable | Human-decision and audit unavailability cases. |
| malicious actor | Forged/cross-bound producer identity case. |
| degraded mode | Limited/degraded artifact versus stronger demanding gate. |
| partial success | Capacity narrower tranche; relation/estimand partial ceilings; compound case remains open. |
| rollback | Stale/withdrawn artifact returns the current case to revalidation without deleting history. |
| historical replay | Old rule/artifact replays historically while current rule requires new evaluation. |
