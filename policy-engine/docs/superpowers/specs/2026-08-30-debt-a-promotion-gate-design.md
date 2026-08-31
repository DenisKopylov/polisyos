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

## 8. Round 2 resolve-and-bind design (approved 2026-08-31)

Round 2 completes the producer handshakes discovered after the v5/v3/v2
repair. The current DTO shape remains authoritative: `producer_root_refs`
carries content-addressed bridge references and `CandidateSummary.value_blockers`
carries N5's typed negative token. Neither field may carry an unverified payload
or a caller assertion.

### 8.1 Typed promotion-evidence bridge

`promotion_sequence.py` owns one strict CAS bridge record with two evidence
kinds: `effective_independence` and `measurement_root`. Each record binds:

- the exact candidate id and candidate content hash;
- the design-problem id, content hash, and rule version;
- the dotted producer owner and immutable source artifact identity;
- raw and semantic source hashes;
- the independently recomputed predicate disposition and limitation code;
- an N9-purpose verifier-provenance reference.

The writer persists canonical bytes, reads them back, verifies the CAS manifest,
and returns a PDC `ArtifactRef` whose `artifact_id` is the real CAS id and whose
`content_hash` binds the bridge record. The reader starts only from a matching
entry in `producer_root_refs`, re-reads exact bytes and verifier provenance,
revalidates the producer-specific source, and checks the candidate/problem
binding before returning an independently reconciled disposition. Missing,
duplicate, malformed, foreign-candidate, foreign-problem, wrong-provenance, or
content-drifted evidence produces a typed nonreceipt and never a positive.

For effective independence, the bridge writer invokes the real
`build_effective_independence_graph`; the reader invokes the real validator and
recomputes the graph from its persisted inputs. A hard-collapse dependency is a
negative disposition. This producer remains `implemented_but_not_orchestrated`
until a production design path invokes the writer and supplies its ref.

For measurement, the writer accepts the full `ArtifactEnvelope` returned by
the real `MeasurementRootProducer`, resolves its existing CAS payload, verifies
the authority manifest/producer/source-contract admission, reconstructs the
MeasurementRoot projection, and binds that source to the candidate/problem.
The production producer already runs; only this promotion binding is missing.

### 8.2 Obligation composition

`_measurement_obligation` and the effective-independence decisive predicate
consume only resolver results. An established result uses the real dotted
owner and source refs. A negative producer result is `failed`; missing or
unresolvable evidence is `scope_insufficient` with
`evidence_not_established`. The caller cannot choose any of those states.

The resolver is an orchestration dependency, not a serialized input field. The
N9 owner port constructs it from `PromotionRuntime.store`; direct contract
runners and receipt validators accept it explicitly. Replay without the same
owner store fails closed.

### 8.3 Additive N5 coupling bridge

`_joint_simulation_port_outcome` already consumes N5's content-bound
`feedback_classification`. When its support status is `unsupported`, it appends
exactly `n5_coupling_blocked` without replacing specific diagnostics or
changing control flow. `_summary_with_value_observation` receives the existing
simulation observation and unions only this typed token into the selected
summary's `value_blockers`; its return type and all existing fields are
unchanged.

N9 refuses COUPLING when the token is present. On the production generation
path, the summary is created only after N5, so token absence is the producer's
supported outcome rather than an invented vocabulary match. Tests cover the
real unsupported classifier, token transport, N9 refusal, and an adjacent
supported N5 control.

### 8.4 Refusal census and honest residual

The measurement fixture reports the complete refusal-reason set and its
`scope_insufficient` subset for four scenario cells: data-only/field-pilot by
production/contract-testing semantics, before and after the bridges. Data-only
and pilot must not be conflated because EvalSafety is not applicable to the
former and promotion-authority evidence is required for the latter.

An absent bridge after this design is absence of evidence, not absence of
semantics. Effective independence needs a production design orchestrator to
invoke the graph writer. Measurement needs the running workspace producer's
envelope to be passed through the promotion binding writer. These honest
nonreceipts are recorded even if the row's negative acceptance signal closes.

### 8.5 Receipt epoch

Round 2 keeps v5/v3/v2. The existing v2 epoch explicitly introduced truthful
owner resolution and is still provisional on this unmerged branch. Resolving a
different owner outcome changes the hashed obligation rows, gate hash, and
receipt identity, as intended, while leaving the typed owner projection and
instance-scope algorithm unchanged.

The compatibility proof uses authentic pre-Round-2 v5 bytes: exact structural
round-trip succeeds, current owner replay refuses the stale result, and a
fresh resolved-owner receipt rekeys the owner-derived hashes. This is history
readability, not migration or current authority. EFFECT and the EvalSafety
safety core are outside this mechanism and remain byte-identical.

## 9. Round 3 EFFECT referent ruling

Round 3 separates specification authority from implementation evidence. The
current enum, input DTO, obligation function, and import graph may corroborate
a reading, but none decides what GY-N9 was adopted to require. The governing
source is the first revision that introduced GY-N9 and the adopted RACE
obligation taxonomy together, read against its parent and the later CGF
decision.

### 9.1 Historical identity of the obligation

Commit `584bd7b72` introduced both GY-N9's “entailment / grounding (GY-K)”
clause and a typed `O(x)` compiler whose members include separate
`O_effect(x)` and `O_id(x)` sets. `O_effect` binds the declared effect claim or
epsilon to an estimand, requires a causal path or mechanism, and classifies the
effect as entailed, bounded, or explicitly ungrounded. `O_id` instead records
the identification result, assumptions, proof, and statistical risk spend.

RACE's absence of a `z_effect` coordinate does not collapse those two sets.
`z_ground` aggregates active grounding obligations, while the specification
separately requires identification certificates. Reading the status vector as
the obligation-class denominator is a proxy error. The later CGF decision
assigns GY-K the role of a per-axis typed grounding witness, never an
independent decider and never a substitute for the effect predicate.

The binding outcome is therefore outcome 3: `EFFECT` remains a distinct
obligation and must receive a referent and evaluator supplied by the adopted
`O_effect` contract. It is neither an early spelling of `IDENTIFICATION` nor a
misnamed `ADMISSIBILITY` slot.

### 9.2 Future evaluator contract

The future evaluator must resolve an immutable producer artifact, verify
fixed N9-purpose provenance, bind candidate, problem, epoch, and estimand, and
independently recompute all three `O_effect` predicates. A positive result
requires:

1. the declared effect threshold or claim is mapped to the governed estimand;
2. the applicable causal path or mechanism is grounded for the same scope;
3. the effect claim is entailed or bounded by that grounding.

An explicitly ungrounded result is a decisive negative. Missing, malformed,
foreign, stale, self-attested, or content-drifted evidence is
`evidence_not_established`. A GY-K reference by itself is never sufficient.
This specification does not appoint or implement the producer; that remains a
separate governed slice.

### 9.3 Version and compatibility rule

The v2 scope design explicitly deferred EFFECT semantics. Landing the future
evaluator therefore changes a hashed obligation rule and requires
`n9_obligation_scope.v3` plus `n9_promotion.v6`. Existing v5/v3/v2 receipts
remain structurally readable history and remain inadmissible as current
authority. Extending the strict promotion-evidence union with an effect kind
requires `n9_evidence_bridge.v2`; v1 remains readable. The existing
`producer_root_refs` carrier is sufficient, so the selected design does not
change the owner-projection shape and retains `n9_owner_projection.v3`.

Phase 2's orchestration of the already-defined independence and measurement
writers changes neither the rule epoch nor any receipt shape. It stays within
v5/v3/v2.

### 9.4 Capability and pattern ruling

The EFFECT capability is `producer_missing + artifact_missing +
bridge_missing + consumer_evaluator_missing`; the class and historical
semantic contract exist, but the admitted evidence chain does not. The
independence writer remains `bridge_missing +
implemented_but_not_orchestrated`, while the measurement writer is
`bridge_missing` against a producer already running in production. These
absence kinds must remain separate.

Relevant pattern controls are P32/P37 for content-bound recomputation and P38
for the status-vector proxy error. The smallest correct future repair is one
resolved `O_effect` evidence path, not a marker ref, caller Boolean, imported
symbol, or reinterpretation of an adjacent obligation.

### 9.5 Phase 2 writer orchestration boundary

The production N9 batch constructs the exact candidate/problem-bound
`CanonicalPromotionInput` before either writer runs. Its non-serialized owner
context may supply one strict effective-independence producer-input record and
one real `ArtifactEnvelope` emitted by `MeasurementRootProducer`. The batch
validates those shapes, invokes the existing repository writers, and appends
only their returned content-addressed refs to `producer_root_refs`. It never
copies the source payload or a caller disposition into the canonical input.

The same repository immediately resolves those refs through source-specific
recomputation and fixed verifier provenance. A producer-negative independence
result is decisive `failed`; an admitted measurement root is decisive
`satisfied`. Missing, malformed, foreign, or unreadable writer input adds no
ref and therefore remains the existing `evidence_not_established` refusal.
Pre-existing same-kind refs are not replaced, so duplicate evidence still
fails closed under the reader's exact-one rule.

This is orchestration inside the current v5/v3/v2 epoch: it changes neither a
receipt field nor a semantic rule. `generation_cycle.py` requires no Round-3
change; its already-additive Round-2 dependency threading remains intact.
