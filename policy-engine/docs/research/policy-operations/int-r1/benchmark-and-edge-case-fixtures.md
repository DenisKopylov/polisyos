---
title: INT-R1 — Mutation, Metamorphic, and Edge-Case Benchmark Specification
status: delivered
kind: deep-research
research_task: INT-R1
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r1-amendment
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
amended_after_audit: research/int-r1-independent-audit@0893a739e4739a6cd31dd95bc0b88526e1ff29ae
authoritative_for:
  - research-level benchmark protocol for decisive-obligation omission and validator-fault detection
  - research-level definition of the authority consequences required when the conditional delta claim turns red
  - implementation-neutral mutation, metamorphic, lifecycle, and edge-case catalogue
  - explicit GY-GAP1 and S0-GAP-02 dependencies preventing current benchmark passage
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - authority grant
  - capability claim
  - current issuance of bounded_complete
  - legal compliance conclusion
  - benchmark passage
  - evidence that any fixture or test currently exists
  - evidence that OM-01 is executable against current N9
  - evidence that the mutation operator set is exhaustive
research_only: true
---

# INT-R1 — Mutation, Metamorphic, and Edge-Case Benchmark Specification

## 1. Benchmark standing after audit

The benchmark asks whether the **protected authority property** changes when an obligation or
validator property is removed while superficial structure remains green. It does not ask whether
a document contains `unknown_remainder`, whether all 15 coarse classes are present, or whether a
string such as “accessible” appears.

Two mandatory falsifier families remain:

1. remove a decisive source-derived obligation instance while its source remains and another
   instance keeps the same coarse class populated; and
2. inject a validator fault that makes a decisive failed/unknown obligation appear satisfied.

Both must make the conditional δ claim unusable for the same protected action and public claim.

**Current standing:** no INT-R1 benchmark has been implemented or run. The capability remains
`semantic_test_missing`. Independent scoring remains blocked on S0-GAP-02. The decisive-instance
operator `OM-01` is additionally **blocked on GY-GAP1** because current N9 has no obligation-
instance identity or pre-class aggregation layer. This file specifies the intended property and
the interface gap; it does not represent OM-01 as runnable today.

The nearest existing machinery remains:

- formal invariants with named owners, properties, evidence, revisit triggers, and negatives
  (`policy-engine/src/polisyos/runtime/quality/formal_invariants.py:23-105`);
- N9 receipt/refusal/promotion recomputation
  (`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:1320-1900`); and
- confidence-ledger binding of maintained assumptions
  (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:37-50`).

None is an independent source-to-obligation oracle.

## 2. What “δ proof red” means

A red result does not necessarily mean the e-process arithmetic was recomputed incorrectly. It
means a maintained assumption needed to rely on the inequality for authority has a witnessed
breach or lacks admissible support.

A later implementation must produce the semantic equivalent of:

```python
class ConditionalProofRedReceipt(TypedDict):
    schema_name: Literal["ConditionalProofRedReceipt"]
    schema_version: str
    receipt_id: str
    receipt_content_hash: str
    affected_coverage_envelope_ref: str
    affected_confidence_ledger_receipt_ref: str | None
    affected_promotion_or_claim_ref: str

    proof_color: Literal["red"]
    breached_or_unverified_assumption: Literal[
        "obligation_completeness",
        "validator_soundness",
        "both",
    ]
    fault_class: str
    fault_witness_refs: tuple[str, ...]
    independent_fault_detection_oracle_ref: str
    fault_detection_time: str

    coverage_assessment: Literal[
        "known_incomplete",
        "open_world_unresolved",
    ]
    existing_status_effect: Literal[
        "failed",
        "unknown",
        "scope_insufficient",
    ]
    protected_action_allowed: Literal[False]
    current_public_claim_allowed: Literal[False]
    suspension_or_withdrawal_required: Literal[True]
    revalidation_or_reissue_required: Literal[True]

    arithmetic_receipt_preserved_for_history: bool
    historical_replay_ref: str
    public_notice_reason_code: str

    authoritative_for: tuple[str, ...]
    may_not_use_for: tuple[str, ...]
    research_only: bool
```

Required propagation:

```text
independent fault witness
  -> maintained-assumption breach or unverified standing
  -> known_incomplete or open_world_unresolved
  -> existing failed / unknown / scope_insufficient
  -> protected_action_allowed = false
  -> current_public_claim_allowed = false
  -> current green delta projection removed or suspended
  -> append-only perturbation and revalidation/reissue
  -> old artifacts retained for historical replay
```

A warning, dashboard badge, or auxiliary red report with the protected action/public claim still
green is a benchmark failure.

## 3. Oracle design and anti-self-attestation

### 3.1 Frozen pre-run inputs

Every case freezes before the implementation under test runs:

1. **immutable synthetic source corpus** — stable source IDs, text/structure, scope, effective
   times, authority roles, and hashes;
2. **independently authored expected source-to-obligation oracle** — instance identities,
   derivations, materiality, expected predicate outcomes, and existing-lattice effect;
3. **validator expected-result oracle** — sealed positive/negative/unknown witnesses independent
   of the primary validator; and
4. **mutation manifest** — operator, injection point, preserved markers, expected red chain, and
   version/hash.

The implementation under test may not generate its expected obligations or expected predicate
outcomes.

### 3.2 Independence requirements

At minimum:

- corpus and expected mapping are authored/reviewed separately from the implementation owner;
- evaluator reads the immutable source corpus, not the primary compiler's output list;
- omission oracle compares semantic source-derived instance identities with pre-aggregation
  implementation output;
- validator oracle uses a known negative/unknown witness and a separate predicate or sealed
  result;
- shared parser, ontology, index, rule library, generator, validator code, and data dependencies
  are disclosed;
- at least one common-mode dependency is deliberately faulted;
- expected results/manifests are hash-frozen before execution; and
- an independent scorer signs the final result and surviving-mutant ledger.

A second function importing the same faulty validator is common-mode replay, not independence.

### 3.3 S0-GAP-02 dependency

The Stage-0 kernel leaves independent benchmark scoring/oracle work unresolved rather than
permitting self-scoring to grant passage
(`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:188-212`).
Therefore:

```text
independent scorer current and admitted = required for governed passage
current status = missing
```

No benchmark result may be described as governed, passed, or authority-bearing until S0-GAP-02
is closed by its owner.

## 4. GY-GAP1 and the decisive-instance operator

### 4.1 Actual mismatch with current N9

Current N9 creates one `PromotionObligationRecord` per coarse
`PromotionObligationClass`. The record carries `obligation_class` and `gate_id` but no stable
source-derived obligation-instance identifier. There is no current collection in which two
obligations can share a coarse class before aggregation.

`OM-01` requires:

- two distinct obligation instances in the same class;
- removal of one decisive instance after source derivation;
- preservation of its source in the source manifest;
- preservation of the same coarse class through the second instance; and
- independent comparison before class aggregation.

The downstream GY plan records this missing capability as **GY-GAP1** and says the INT-R1
falsifier cannot execute against the current representation
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:7`).

### 4.2 Amendment decision

The selected disposition is:

```text
OM-01 = conceptually required, currently blocked
blocking gap = GY-GAP1
current benchmark passage = impossible
```

This research does not choose a final schema. To make the property executable, a later owner must
provide at least:

1. a source-derived pre-aggregation obligation-instance collection;
2. stable semantic instance identity binding source, rule, scope, time, predicate, and version;
3. an instance-to-existing-class aggregation rule;
4. an injection point at which one instance can be removed without removing its source or class;
5. an independent expected-instance set derived from the frozen source corpus; and
6. propagation from instance mismatch through the existing lattice, promotion, current δ use,
   public projection, lifecycle, and replay.

Until those exist, agents may implement corpus/oracle prototypes but may not claim OM-01 ran
against governed N9 or that the mandatory omission benchmark passed.

## 5. Canonical synthetic proving fixture

### 5.1 Scenario `F-BASE-COOLING-CENTERS`

The fixture is synthetic. It tests custody and authority semantics, not real legal compliance.

**Protected action.** Publish a PolicyOS claim that a municipal heatwave cooling-center policy is
promotion-ready for synthetic jurisdiction `J-ALPHA`, population `all residents`, episode
`E-2042`.

**Frozen source corpus.**

| Source ID | Family | Synthetic rule | Expected obligation instance | Decisive? |
| --- | --- | --- | --- | --- |
| `JA-ORD-01` | normative/legal | A promotion-ready design must provide independently verified accessible venue coverage in every district. | `O-ACCESS-EACH-DISTRICT` | yes |
| `JA-MET-02` | measurement | Trigger thresholds use a calibrated heat-index feed valid through the episode. | `O-HEAT-INDEX-CALIBRATION` | yes |
| `JA-IMP-03` | implementation | Capacity/hours attestations come from the named competent facilities owner and remain current. | `O-CAPACITY-OWNER-ATTESTATION` | yes |
| `JA-VAL-04` | value/normative | Analysis reports district-level access disparity and accepted deficits. | `O-DISTRICT-DISPARITY` | yes for unconditional equity claim; otherwise limitation |
| `JA-DAT-05` | data | Population denominators bind census snapshot, revision, and missingness. | `O-POPULATION-SNAPSHOT` | yes |
| `JA-SYN-06` | syntax/type | Venue intervention binds operator, target slot, effect bundle, and intended effect. | `O-INTERVENTION-ATOM-SHAPE` | yes |
| `JA-GOV-07` | governance | Publication links coverage record, validator governance, expiry, and challenge route. | `O-COVERAGE-PUBLIC-RIDER` | yes |

**Candidate `D-GOOD`.** Contains the synthetic positive evidence expected by all seven rules.

**Candidate `D-MISSING-ACCESS`.** Is identical except district 3 lacks independently verified
accessible venue evidence. It retains a generic accessibility statement.

### 5.2 Future benchmark expectations, not current capability

When the required instance layer, independent scorer, governance records, and bridges exist:

- `D-GOOD` may be the fixture-only positive baseline relative to this frozen corpus; every
  substantive obligation must independently satisfy and the public rider remains conditional.
- `D-MISSING-ACCESS` must yield
  `O-ACCESS-EACH-DISTRICT = failed`, promotion false, and current δ claim unusable.

At the present repository neither candidate may establish current `bounded_complete`: independent
coverage capability and scoring are missing. A prototype runner must label the positive baseline
as synthetic/future-target only.

### 5.3 What superficial checks the fixture defeats

`O-ACCESS-EACH-DISTRICT` and `O-DISTRICT-DISPARITY` share the coarse `normative` class. In the
future instance model, deleting the decisive accessibility instance leaves the class populated by
the disparity instance. The bad candidate also retains generic accessibility text.

Thus the fixture is designed to defeat:

- pure 15-class counting;
- presence of a normative row;
- source-manifest marker presence without instance comparison; and
- generic accessibility-token checks that do not bind district-level source semantics.

It does **not** claim to defeat every possible “keyword test” or an undefined semantic oracle.

## 6. Mutation operators

### 6.1 Obligation discovery and compilation faults

| ID | Mutation | Preserved markers | Required independent detection | Required red reason | Current executability |
| --- | --- | --- | --- | --- | --- |
| `OM-01` | Delete `O-ACCESS-EACH-DISTRICT` after source derivation, before validation. | source remains; normative class remains; all 15 classes may remain | frozen source-to-instance set mismatch before aggregation | `decisive_obligation_omitted` | **blocked on GY-GAP1** |
| `OM-02` | Change query/filter so `JA-ORD-01` is not returned. | query succeeds; result set nonempty | required-source manifest/query-result mismatch | `required_source_not_searched` | design-only |
| `OM-03` | Mis-scope `JA-ORD-01` to `J-BETA`. | source bytes/hash unchanged | independent applicability oracle | `obligation_scope_misclassified` | design-only |
| `OM-04` | Map accessibility rule to `not_applicable_data_only`. | record shape and enum valid | family/status semantic rule | `invalid_not_applicable_conversion` | design-only |
| `OM-05` | Collapse accessibility and disparity as one normative item. | one normative result/class totality | distinct source-rule semantic identities | `distinct_obligations_collapsed` | requires instance layer |
| `OM-06` | Use pre-effective snapshot while declaring later cutoff. | resolver succeeds | source-effect/cutoff consistency | `snapshot_cutoff_mismatch` | design-only |
| `OM-07` | Exclude `JA-ORD-01` without competent authorization/materiality. | exclusion field present | exclusion governance evidence | `unauthorized_material_exclusion` | design-only |
| `OM-08` | Skip nested exception that creates an obligation. | source hash/top-level count remain | generic recursive traversal mutation | `nested_obligation_path_skipped` | design-only |
| `OM-09` | Launder unavailable required source as empty success. | no transport error | availability/provenance distinction | `unavailable_source_laundered_as_empty` | design-only |
| `OM-10` | Reuse old envelope after adding a district. | candidate largely unchanged | scope identity/hash rule | `scope_expansion_without_reassessment` | design-only |

`OM-01` remains the mandatory decisive-instance falsifier, but the mandatory gate cannot be
satisfied until GY-GAP1 closes.

### 6.2 Validator faults

| ID | Mutation | Negative witness | Required red reason |
| --- | --- | --- | --- |
| `VM-01` | Accessibility validator always returns satisfied. | `D-MISSING-ACCESS` | `validator_always_true` |
| `VM-02` | Invert failed and satisfied. | one frozen positive and one frozen negative | `validator_result_inverted` |
| `VM-03` | Convert unresolved venue evidence to satisfied. | missing/unresolvable evidence ref | `unknown_laundered_as_satisfied` |
| `VM-04` | Check generic word “accessible,” not district-level verified evidence. | generic statement present; district 3 evidence absent | `form_based_validator` |
| `VM-05` | Trust candidate self-attestation as owner evidence. | owner-like text without competent signature | `candidate_authority_laundering` |
| `VM-06` | Use superseded rule version. | current corpus plus stale rule hash | `validator_rule_version_stale` |
| `VM-07` | Independent checker imports the mutated primary validator. | shared component disclosed | `independent_check_common_mode` |
| `VM-08` | Loop-bound fault skips final district. | violation placed in last district | `validator_iteration_incomplete` |
| `VM-09` | Ignore contradictory owner evidence/revocation. | positive and revocation both present | `contradictory_evidence_ignored` |
| `VM-10` | Governance remains “current” after validator hash changes. | implementation hash mutation | `unreviewed_validator_change` |

`VM-01` or an equivalent semantic fault is mandatory. A primary satisfied record does not prevent
red if the independent oracle exposes the fault.

### 6.3 Governance, closure, time, and projection faults

| ID | Mutation | Required result |
| --- | --- | --- |
| `GT-01` | Expire source/validator review while substantive outputs stay green. | unresolved/scope-insufficient; protected action and public claim false |
| `GT-02` | Producer and reviewer are same conflicted owner without admitted mitigation. | independence unresolved; no positive assessment |
| `GT-03` | Mark an `independence_record` complete without evidence. | self-attestation rejection; unresolved |
| `GT-04` | Claim `closed_by_competent_basis` without owner mandate or exact scope. | closure not established; protected use false |
| `GT-05` | Reuse a closure premise outside its jurisdiction/purpose/interval. | scope mismatch; unresolved or known incomplete |
| `GT-06` | Accept material post-publication challenge without suspending current claim. | lifecycle test fails; red and reissue required |
| `GT-07` | Rewrite old envelope to include new obligation. | append-only/history test fails |
| `GT-08` | Render `risk <= delta` without declared-set rider/remainder/expiry. | projection fails even if backend arithmetic is correct |
| `GT-09` | Reissue with unchanged identity after source set changes. | content/identity test fails |
| `GT-10` | Transported challenge event sets withdrawn without canonical owner decision. | no-authority-by-transport invariant fails |
| `GT-11` | Historical replay at `t0` uses current sources/validators. | replay isolation fails |
| `GT-12` | Persist/render `NO_COVERAGE_BLOCKER` as a status. | one-lattice test fails; benchmark invalid |

## 7. Metamorphic laws

| ID | Transformation | Required relation |
| --- | --- | --- |
| `ML-01` | Reorder semantically identical source entries. | obligation set/decision invariant; canonical hash invariant if canonical order defined |
| `ML-02` | Duplicate same snapshot/evidence. | confidence and authority do not increase; dedupe explicit/idempotent |
| `ML-03` | Add applicable unsatisfied decisive obligation. | authority cannot improve; promotion/current claim false |
| `ML-04` | Remove decisive instance while source remains. | current proof turns red; **execution blocked until GY-GAP1** |
| `ML-05` | Add irrelevant out-of-scope source. | substantive result invariant; source handling auditable |
| `ML-06` | Expand jurisdiction/population/time/purpose/audience. | old envelope cannot be reused; fresh closure/search/review required |
| `ML-07` | Narrow scope. | improved result needs new scope identity/envelope; no silent mutation |
| `ML-08` | Advance beyond earliest decisive TTL. | result stays same or degrades, never upgrades; current use blocked |
| `ML-09` | Semantics-preserving reviewed validator refactor. | outcomes equivalent across frozen fixture battery |
| `ML-10` | Replace competent source with unverified mirror of identical bytes. | content equality does not preserve authority; result degrades |
| `ML-11` | Discover missed obligation after publication. | `t0` replay stable; current projection suspends and reissue opens |
| `ML-12` | Insert mutually conflicting applicable obligations. | preserve both; no collapse to satisfied; conflict routes fail-closed |
| `ML-13` | Remove competent owner/mandate while retaining rule text. | no bounded current result where competence is decisive |
| `ML-14` | Replace admitted evidence with candidate self-description. | candidate firewall prevents authority upgrade |
| `ML-15` | Remove only public conditional rider. | projection fails; public claim cannot stay green |
| `ML-16` | Semantic-preserving serialization change under declared normalization. | semantic set invariant; raw provenance/version still changes |
| `ML-17` | Replace `closure_not_established` with `closed_by_competent_basis` but add no evidence. | assessment cannot improve; self-attested closure rejected |
| `ML-18` | Change scorer/oracle after observing outcomes. | old run invalid; new frozen benchmark version required |

Passing these laws is adequacy relative to the declared transformations, not proof of a complete
fault or obligation universe.

## 8. Required edge-case fixtures

### `F-01` — Future positive baseline

**Input.** `D-GOOD`; synthetic sources current; closure disposition/evidence declared; independent
review, scorer, governance, instance layer, and bridges exist in the future fixture environment.

**Expected.** Future fixture-only relative positive state; every substantive obligation separately
satisfied; public rider retains basis/language/assumptions/remainder/expiry. Removing the rider
fails projection.

**Current caveat.** This is not runnable as a governed positive benchmark at the pinned repository
and is not evidence of current `bounded_complete`.

### `F-02` — Decisive obligation missing

**Input.** `D-MISSING-ACCESS`; apply `OM-01` after GY-GAP1 closes.

**Expected.** Frozen source-to-instance oracle detects missing
`O-ACCESS-EACH-DISTRICT`; `known_incomplete`; existing failed or scope-insufficient; promotion
false; both red booleans false; reason `decisive_obligation_omitted`.

**Unsafe conclusion rejected.** “All 15 classes are present, therefore coverage holds.”

**Current caveat.** Blocked on GY-GAP1.

### `F-03` — Late-discovered obligation after publication

Publish under corpus v1. At `t1`, admit a challenge proving an already-applicable backup-power
rule was omitted at `t0`.

Expected: original envelope/receipt immutable and replayable; current use challenged/suspended;
`known_incomplete`; proof red; perturbation and reissue; public correction links history.

### `F-04` — Validator later found unsound

A validator used by the future positive fixture is later shown by `VM-08` to skip the final
district.

Expected: governance `known_unsound`/suspended; affected envelopes found; current use stopped;
`known_incomplete`; validator-soundness red; independent revalidation before any reissue.

### `F-05` — Two obligations conflict

Add a synthetic contamination rule requiring closure where another rule requires an open
accessible venue.

Expected: preserve both obligations and provenance; no dedupe/silent priority; absent competent
conflict rule/owner, existing unknown/failed/scope-insufficient and promotion false.

### `F-06` — Obligation owner unavailable

Capacity rule exists but named facilities owner/mandate cannot be verified.

Expected: source/owner unavailable or competence unresolved; `open_world_unresolved` or
`known_incomplete` for a known required owner; existing scope-insufficient; candidate work may
continue with limitation; protected action false.

### `F-07` — Degraded mode

A nondecisive explanatory source is unavailable. The stopping rule permits reviewer-only
candidate output, not public promotion.

Expected: purpose-scoped limitation; no global bypass; public protected action remains blocked if
the source is required for that audience.

### `F-08` — Partial success

Districts 1–2 satisfy all obligations; district 3 remains unknown; declared scope is all districts.

Expected: whole-scope claim not promoted. A legitimate narrower candidate requires new scope
identity, closure disposition, basis, and review. No UI slicing or silent denominator change.

### `F-09` — Rollback/suspension

Material challenge from `F-03` is accepted while a public claim is displayed.

Expected: stop current use, append suspension/correction, notify competent external owner, open
reissue. Do not delete old receipt or execute municipal rollback.

### `F-10` — Historical replay

Query the claim at `t0` after a replacement at `t2`.

Expected: old snapshots/rules/validators/assessment/publication reproduced; later correction
lineage visible without contaminating `t0`; current query resolves replacement/suspension.

### Additional adversarial fixtures

| ID | Condition | Expected outcome |
| --- | --- | --- |
| `F-11` | Required query silently paginates only first page. | known incomplete/unresolved; red |
| `F-12` | Same rule appears in two sources with different effect times. | preserve both temporal/provenance roles; no blind dedupe |
| `F-13` | Source bytes identical after competent revocation. | current authority degrades despite content equality |
| `F-14` | Cryptographically valid challenge is outside scope. | reject out-of-scope with retained record; no unrelated reaction |
| `F-15` | Material challenge unresolved by deadline. | suspended; inconclusive is not pass |
| `F-16` | Validator tests pass but independent governance expired. | no current positive assessment |
| `F-17` | Public compression hides material exclusion/remainder. | projection fails |
| `F-18` | Required source family has no canonical owner. | explicit owner gap; no research-created owner |
| `F-19` | Closure register is competent nationally but not municipally. | closure not transferable; local scope unresolved |
| `F-20` | Producer self-signs closure and independence evidence. | P29 failure; no positive assessment |
| `F-21` | `NO_COVERAGE_BLOCKER` serialized as a public status. | benchmark invalid; parallel-lattice breach |
| `F-22` | Attempt positive baseline before S0-GAP-02 or GY-GAP1 closes. | explicit blocked result, never simulated pass |

## 9. Implementation-neutral package

Illustrative only; not a package-placement decision:

```text
int_r1_benchmark/
  corpus/
    JA-ORD-01.*
    JA-MET-02.*
    JA-IMP-03.*
    JA-VAL-04.*
    JA-DAT-05.*
    JA-SYN-06.*
    JA-GOV-07.*
  fixture-manifest.yaml
  scope-purpose-audience-cutoffs.yaml
  closure-premise-evidence.yaml
  expected-source-to-obligation-instances.yaml
  expected-source-to-obligation-derivations.yaml
  expected-instance-to-class-aggregation.yaml
  candidate-D-GOOD.yaml
  candidate-D-MISSING-ACCESS.yaml
  validator-expected-results.yaml
  mutation-manifest.yaml
  metamorphic-law-manifest.yaml
  expected-authority-propagation.yaml
  public-projection-expectations.yaml
  history-replay-expectations.yaml
  independence-evidence.yaml
  scorer-governance.yaml
```

The pre-run root binds every file, scorer/evaluator version, and expected result. The runner records
implementation commit/configuration, source/query/rule/compiler/validator/governance hashes,
closure disposition, mutation and injection point, primary and independent results, pre-
aggregation instance comparison, class aggregation, existing-lattice effect, promotion/current δ
use, public projection, lifecycle/history result, and mutant disposition.

## 10. Execution protocol and dependency gates

### Phase 0 — prerequisite gate

Before any claim of governed execution:

- S0-GAP-02 independent scorer/oracle governance is current and admitted;
- GY-GAP1 instance identity/aggregation and injection/comparison points exist;
- coverage/governance producers and N9/N11/N12/claim bridges exist;
- the one-lattice and public projection integration is testable; and
- the positive baseline is not a self-attested simulation.

If any is absent, emit a blocked receipt and stop. Do not skip to “pass.”

### Phase 1 — freeze

Freeze corpus, scope/purpose/audience/cutoffs, closure evidence, expected instances/derivations,
validator results, mutations, metamorphic laws, propagation expectations, independence evidence,
and scorer version.

### Phase 2 — baselines

Run future `F-01` positive and unmutated `D-MISSING-ACCESS` negative. Verify full capability chain
and public rider.

### Phase 3 — mandatory mutations

Run `OM-01` and `VM-01`/`VM-04`. Require independent detection and complete red propagation.
Run `VM-07` to reject same-path common-mode checking.

### Phase 4 — metamorphic/lifecycle/edge batteries

Run `ML-01`–`ML-18`; `F-03`, `F-04`, `F-09`, `F-10`; and remaining edge cases. Record exact
existing-lattice outcomes and history.

### Phase 5 — independent scoring

The independent scorer signs all fixture results, invalid-run reasons, surviving material mutants,
equivalence rationales, common-mode findings, and dependency standing.

## 11. Acceptance and kill rules

### 11.1 Benchmark acceptance signal

A later implementation may claim passage only when:

- prerequisite gate is green, including GY-GAP1 and S0-GAP-02;
- every mandatory fixture has a content-bound result;
- `OM-01` and `VM-01` make the full protected claim red;
- no material mutant survives without independently accepted equivalence rationale;
- no checker relies solely on class, shape, marker, or generic token presence;
- shared dependencies are disclosed and common-mode faults are detected;
- incomplete/unresolved results feed the one existing lattice;
- `protected_action_allowed = false` and `current_public_claim_allowed = false` for every affected
  decisive fault;
- public green projection is removed/suspended and the relative rider is preserved;
- later discovery and validator incidents cause append-only suspension/reissue;
- historical replay is reproducible; and
- independent scorer/governance are current.

### 11.2 Immediate invalidation rules

The benchmark is invalid—not merely failed—if:

- expected results come from the implementation under test;
- source-to-obligation comparison occurs only at the 15-class level;
- OM-01 is claimed before GY-GAP1 supplies the instance/injection/comparison layer;
- the omission mutation removes the source as well as the obligation, defeating the intended
  discovery-versus-validation distinction;
- a producer-filled independence field substitutes for evidence;
- missing/expired scorer or oracle is treated as green;
- the protected action or public claim stays green after a decisive fault;
- a red auxiliary artifact is counted without authority propagation;
- `NO_COVERAGE_BLOCKER` becomes a persisted/rendered status;
- mutation/expected results change after observation without a new frozen version;
- old envelopes are edited in place; or
- passage is represented as world completeness, compliance, competence, or current
  `bounded_complete` capability.

## 12. Evidence boundary

If implemented and independently passed, the benchmark could support only that:

- the implementation detects the declared omission and validator fault models;
- source-to-obligation instance coverage is behaviorally connected to existing status, promotion,
  current δ use, and public projection;
- challenge/reissue/history satisfy the declared fixture properties; and
- the tested mechanism is not merely a class/marker/generic-token check for those faults.

It cannot support that the mutation set is exhaustive, every world obligation is discoverable, a
real jurisdiction is legally closed, every validator is sound outside the fixture domain,
PolicyOS is compliant/authorized, or the unknown remainder is empty or below δ.

**Final standing:** no benchmark was implemented or run in this research/amendment pass.
`semantic_test_missing` remains accurate. `OM-01` is blocked on GY-GAP1; governed scoring is
blocked on S0-GAP-02; current `bounded_complete` is unavailable.
