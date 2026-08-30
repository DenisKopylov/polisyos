# Debt A Promotion Gate — Governed v5/v2 Design

## 1. Decision and authority boundary

The governed change is a new N9 authority epoch, not a string correction.
`n9_obligation_scope.v2` changes obligation records and therefore changes
obligation instance IDs, `_gate_outcome_hash`, replay results, and every
receipt derived from them. Current input and receipt authority advance from
`n9_promotion.v4` to `n9_promotion.v5`. Authentic v4 receipts remain exact,
readable history under `n9_obligation_scope.v1`; they cannot be admitted,
restamped, or automatically migrated into v5 authority.

This design changes neither the 15-member `PromotionObligationClass` set nor
the `PromotionObligationStatus`/`PromotionFailClosedReason` lattices. EFFECT is
not renamed, interpreted, corrected, or used as a test control. The
attempted-evaluation safety core and its hashes are outside this design.

## 2. Measured predicate ownership

### 2.1 Admissibility

The existing authority chain is:

`GroundingBindGate._obligations(admissibility_closed)` → content-bound
`GroundingDecisionCertificate` → owner-store
`resolve_grounding_decision_promotability` → N9 IDENTIFICATION.

A bind certificate cannot retain an open obligation. N9 then resolves the
certificate against the exact credal reference, reference epoch/hash, owned
anchor, content hash, and authority scope. This is the real admissibility
producer and consumer. `CanonicalPromotionInput.admissibility: bool = True`
adds no evidence and has no legitimate current role.

Current v5 removes the Boolean. Direct Pydantic construction rejects it as an
extra field. `CanonicalN9PromotionPort` also rejects the legacy key before it
can be ignored by a context mapping. V4 history retains it solely because it
was present in historical owner bytes.

### 2.2 Effective independence

The repository has generic effective-independence calculations, but no
candidate-bound, persisted, N9-purpose artifact with a resolver and verifier
provenance. The committed G5 structural record is not positive N9 evidence.
Therefore v5 removes the caller Boolean and emits an explicit
`decisive_predicate` non-receipt with:

- status `scope_insufficient`;
- reason `scope_insufficient`;
- semantic scope `scope_insufficient`;
- a source reference owned by the N9 absence detector;
- owner `absent/unallocated` until an N9-purpose producer is appointed;
- detail that names `producer_missing`, not a failed evidence lookup.

This fixes false grant while leaving the debt row open. A later producer must
carry candidate/problem binding, provenance, rule/schema version, relevant
time/currentness, and a verifier receipt. A caller-shaped map or `True` cannot
be that producer.

### 2.3 Coupling

N5 emits real negative evidence as typed
`SimulationPortObservation.authority_blockers`, including values such as
`unsupported_coupling_class:feedback`. N9 currently reads two strings that no
source producer emits from a different field and treats their absence as
success. Expanding the string list would be a P31/P33 instance patch.

Until a candidate-bound N5 or verified S5 composition projection is carried
into N9, COUPLING returns `scope_insufficient`, never `satisfied`. Its owner
detail says `bridge_missing`. A unit test carries the real N5 spelling only to
prove it cannot be mistaken for a pass; it does not manufacture the missing
bridge. Closure still requires production assembly to transport and verify the
typed outcome.

### 2.4 Measurement

`polisyos.runtime.quality.data_forge_binding.MeasurementRootProducer` is a real
CAS-backed producer. The gap is not an absent owner: ValueGateReceipt and N9
carry no candidate/current-problem measurement-root resolution. MEASUREMENT
therefore remains `scope_insufficient`, with a dotted producer owner and detail
`bridge_missing`. A value-receipt marker remains inadmissible.

### 2.5 Evaluation safety

Attempted-evaluation safety is already produced, persisted, replayed, and
verified before non-simulation evaluator work. Its certificate is explicitly
authoritative for attempted-evaluation admission and explicitly forbidden for
promotion. Importing that certificate into N9 as a positive promotion
predicate would be an authority leak, not orchestration.

For pilot/deployment ValueGateReceipts, EVAL_SAFETY remains fail-closed and its
detail states that no promotion-authoritative predicate exists. For data-only
modes it remains `not_applicable_data_only`. No safety-core field, hash, or
certificate envelope changes.

## 3. Versioned receipt model

### 3.1 Current types

- `CanonicalPromotionInput.schema_version = n9_promotion.v5`
- `CanonicalPromotionReceipt.schema_version = n9_promotion.v5`
- `CanonicalPromotionOwnerProjection.schema_version = n9_owner_projection.v3`
- `_PROMOTION_OBLIGATION_SCOPE_RULE_VERSION = n9_obligation_scope.v2`

Owner projection v3 is required because current owner bytes remove
`admissibility` and `effective_independence`. It otherwise preserves the exact
current v2 owner fields and validators.

### 3.2 History types

- `_LegacyCanonicalPromotionOwnerProjectionV2` preserves the exact v4 owner
  shape, including both inert Booleans, `open_world_gate`, and epoch validity.
- `_LegacyCanonicalPromotionReceiptV4` preserves v4 plus owner projection v2.
- Existing v3/v1 and v2/v1 history types remain readable.

`parse_canonical_promotion_history_receipt` dispatches v5/v4/v3/v2. Current
authority validators accept only v5. Historical receipts return a typed
non-admission; parsing is never promotion authority.

### 3.3 Scope and restamp verification

Every current obligation row must carry the one recomputed v2 instance-scope
hash for its exact input. Validation compares each row's
`instance_scope_content_hash` to that expected hash in addition to recomputing
the row identity. This closes the case where an authentic v4/v1 receipt is
restamped v5 while retaining internally self-consistent old row IDs and a
rehashed gate outcome.

The current comparison projection rule advances with the current typed receipt
owner. The immediately preceding comparison rule remains registered for v4
history. No history projector may convert v4/v1 semantics to v5/v2 current
authority.

## 4. Obligation composition

The class-gate denominator stays exactly the live enum order. V5 adds one
decisive effective-independence non-receipt alongside the existing two N8
receipt-consistency predicates. The non-receipt uses an existing class/gate
coordinate only as a typed carrier; it does not claim a new class semantic.
`_refusal_reasons` already composes all failed, unknown, and production
scope-insufficient records, including decisive predicates, so no parallel
decision path is added.

The normal current shapes are:

- no ValueGateReceipt: 15 class gates plus the independence non-receipt;
- ValueGateReceipt: 15 class gates, the independence non-receipt, and two N8
  consistency predicates.

Tests must derive these shapes from the emitted record roles and source refs;
they must not create an independent hard-coded obligation class denominator.

## 5. Test-control repair

The generic `scope_insufficient` anti-vacuity test uses PARAM with
`g4_governed_promotion_ref=None`. PARAM has a real resolvable owner, a real
positive path, and an honest absence path; it is not a constant failure.

The owner-recomputation mutation uses PARAM with a forged G4 record and relabels
that real resolver refusal. It no longer mutates EFFECT or MEASUREMENT. The
mutation must remain red after recomputing the outer gate hash, proving owner
replay rather than hash presence.

Additional adversarial cases:

1. Direct current input with either legacy Boolean is rejected.
2. Context mapping with either legacy Boolean is rejected.
3. An actual CG2 certificate whose admissibility obligation is open cannot
   become promotable.
4. Actual N5 blocker vocabulary and absent N5 evidence both fail to produce a
   satisfied COUPLING row.
5. A v4/v1 receipt parses as history, fails current model validation, and fails
   authority admission.
6. A restamped v4/v1 receipt fails v2 scope recomputation.
7. Fresh v5/v2 replay is deterministic.

## 6. Capability completion and dossier semantics

No row is marked closed merely because minting was replaced by conservative
refusal. Row verdicts follow their registered acceptance signals:

- a producer requirement remains `open` if only its false grant was removed;
- a bridge requirement remains `open` if the typed artifact cannot reach N9;
- a vocabulary requirement remains `open` when the task forbids changing the
  lattice;
- `GY-O0-NC-01` remains `open` until a real current production promotion exists;
- EFFECT remains a separately ruled open investigation.

The final journal supplies append-only register prose for all five rows. It
states the exact tested predicate, direct exit, decisive output, and capability
label. It does not rewrite the protected register.

## 7. Patch/generalise ruling

The initial implementation is narrow because the two defect classes are
different. The generalisation trigger is the first additional spelling of
either class discovered outside the five scoped rows. If triggered, the
mechanism must derive owner resolvability and refusal reachability from source
truth rather than enumerate another owner string or blocker token. Tests and
mandatory plan/journal/generated companions do not consume a mechanism round.
