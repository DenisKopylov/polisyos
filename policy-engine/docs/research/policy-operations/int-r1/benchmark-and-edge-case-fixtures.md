---
title: INT-R1 — Mutation, Metamorphic, and Edge-Case Benchmark Specification
status: delivered
kind: deep-research
research_task: INT-R1
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r1-obligation-coverage
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: d152565dcc11cea457dacd61fadc6e15dc3ecc86
inspection_date: 2026-08-02
authoritative_for:
  - research-level benchmark protocol for decisive-obligation omission and validator-fault detection
  - research-level definition of what it means for the conditional delta proof to turn red
  - implementation-neutral mutation and metamorphic law catalogue
  - required edge-case fixture expectations for later implementation
  - benchmark-oracle independence requirements
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - authority grant
  - capability claim
  - legal compliance conclusion
  - benchmark passage
  - evidence that any fixture or test currently exists
  - evidence that the mutation operator set is exhaustive
research_only: true
---

# INT-R1 — Mutation, Metamorphic, and Edge-Case Benchmark Specification

## 1. Benchmark question

The benchmark does not ask whether a JSON document contains the words `unknown_remainder` or
whether the 15 coarse classes are present. It asks whether the **actual authority property**
changes when the obligation or validator property is removed while superficial markers remain.

The two mandatory falsifiers are:

1. remove a decisive obligation from the compiled obligation set while leaving its source,
   class-level denominator, hashes/markers that are not supposed to change, and the candidate's
   violating behavior intact; and
2. inject a validator fault that makes a decisive failed/unknown obligation appear satisfied.

In both cases, the conditional δ proof must turn **red**. A test that only makes an auxiliary
coverage report red while allowing the same protected promotion or public green chip is a failed
benchmark.

The repository already has the nearest structural machinery: formal invariants require named
owners, protected properties, accepted check types, model properties, evidence, revisit
triggers, and negative tests
(`policy-engine/src/polisyos/runtime/quality/formal_invariants.py:23-105`); the N9 validator
recomputes receipt classes/refusal reasons/promotion
(`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:1320-1900`); and the ledger
binds the maintained assumptions
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:37-50`). INT-R1 requires a
new semantic fault model and an oracle independent of the mutated path; this file does not
implement either.

## 2. Meaning of “the δ proof turns red”

A red result does **not** assert that the numerical e-process or allocation arithmetic was
miscomputed. It asserts that at least one maintained assumption needed to use the inequality as
an authority claim has a witnessed breach or cannot be supported.

A later implementation should produce the semantic equivalent of this research-only receipt:

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
    fault_detection_oracle_ref: str
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

The required propagation chain is:

```text
fault witness
  -> coverage/validator maintained-assumption breach
  -> coverage assessment known_incomplete or open_world_unresolved
  -> existing N9 status failed/unknown/scope_insufficient
  -> protected promotion false
  -> current δ claim unusable
  -> current public green projection removed/suspended
  -> perturbation + revalidation/reissue path
  -> old artifacts retained for historical replay
```

A benchmark is red only if every applicable link is observed. “The test logged a warning” is not
red.

## 3. Oracle design and anti-self-attestation controls

### 3.1 Three frozen inputs

Each benchmark case is frozen before the system under test runs:

1. **source corpus:** human-readable and machine-addressable synthetic source instruments with
   stable IDs, effective times, scope, and hashes;
2. **independent obligation oracle:** a separately authored expected source→obligation mapping,
   including decisive/nondecisive classification and expected existing-lattice result; and
3. **mutation manifest:** fault operators and the exact stage at which each operator is injected.

The system under test may not generate its own expected obligation oracle.

### 3.2 Independence requirements

At minimum:

- corpus/expected mapping reviewed by a person or process distinct from the implementation owner;
- evaluator loads the immutable source corpus, not the primary compiler's already-generated
  obligation list;
- omission oracle compares source-derived expected obligation IDs/semantic fingerprints with the
  system output;
- validator-fault oracle uses a known negative candidate and an independent predicate or sealed
  expected result;
- primary and independent paths disclose shared parser, ontology, source index, rule library, and
  code-generation dependencies;
- common-mode dependencies are deliberately mutated in at least one fixture; and
- expected results and mutation manifests are content-hashed before execution.

An independent checker that imports and calls the same faulty validator is a common-mode replay,
not independent verification.

### 3.3 S0-GAP-02 dependency

The ratified Stage-0 record leaves independent benchmark scoring/open-world benchmark-oracle
work as a live gap rather than allowing self-scoring to grant passage
(`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:188-212`).
Therefore this benchmark can be specified now, but `governed_allowed` requires an independent
oracle owner and scoring protocol ratified through consolidation.

## 4. Canonical synthetic proving fixture

### 4.1 Scenario `F-BASE-COOLING-CENTERS`

The benchmark uses a synthetic jurisdiction and instruments so that the fixture tests custody
semantics rather than making a real legal conclusion.

**Protected action.** Publish a PolicyOS design claim that a municipal heatwave cooling-center
policy is “promotion-ready” for jurisdiction `J-ALPHA`, population scope `all residents`, and
summer episode `E-2042`.

**Declared source corpus.**

| Source ID | Family | Synthetic rule | Expected obligation ID | Decisive? |
| --- | --- | --- | --- | --- |
| `JA-ORD-01` | normative/legal | A promotion-ready cooling-center design must provide an independently verified accessible venue in every district before publication as deployable. | `O-ACCESS-EACH-DISTRICT` | yes |
| `JA-MET-02` | measurement | Trigger thresholds must use a calibrated heat-index feed with calibration valid through the episode. | `O-HEAT-INDEX-CALIBRATION` | yes |
| `JA-IMP-03` | implementation | Capacity and operating-hour attestations must come from the named facilities owner and remain current at publication. | `O-CAPACITY-OWNER-ATTESTATION` | yes |
| `JA-VAL-04` | value/normative | The allocation analysis must report district-level access disparity and accepted deficits. | `O-DISTRICT-DISPARITY` | yes for an unconditional equity claim; otherwise limitation path |
| `JA-DAT-05` | data | Population denominators must bind census snapshot, revision, and missingness. | `O-POPULATION-SNAPSHOT` | yes |
| `JA-SYN-06` | syntax/type | Each venue intervention must bind one operator, one target slot, one direct-effect bundle, and one intended effect. | `O-INTERVENTION-ATOM-SHAPE` | yes |
| `JA-GOV-07` | governance | Publication must link the coverage envelope, validator governance record, expiry, and challenge route. | `O-COVERAGE-PUBLIC-RIDER` | yes |

**Good candidate `D-GOOD`.** Supplies verified accessible venues in every district, current
calibration, competent facility-owner attestations, disparity analysis, content-bound census
snapshot, well-formed intervention atoms, and the required public rider.

**Bad candidate `D-MISSING-ACCESS`.** Is identical except district 3 has no verified accessible
venue. The candidate retains a generic accessibility statement, so keyword/marker tests remain
green. The semantic obligation `O-ACCESS-EACH-DISTRICT` must fail.

**Expected baseline.**

- `D-GOOD`: `bounded_complete` relative to the synthetic corpus; all substantive obligations
  satisfied; promotion may proceed only in the fixture; public rider remains conditional.
- `D-MISSING-ACCESS`: obligation `O-ACCESS-EACH-DISTRICT = failed`; promotion false; δ proof not
  usable for a positive claim.

### 4.2 Why this fixture detects the enum gap

`O-ACCESS-EACH-DISTRICT` and `O-DISTRICT-DISPARITY` can share the same coarse `normative` class.
If the decisive accessibility obligation is removed, the 15-class denominator can remain total
because another normative instance still exists. The existing class-level totality check may
therefore remain green. The INT-R1 oracle must compare source-derived **obligation instances**,
not only enum members.

## 5. Mandatory mutation operators

### 5.1 Obligation-discovery and compilation faults

| ID | Mutation | Markers intentionally preserved | Required detection | Required red reason |
| --- | --- | --- | --- | --- |
| `OM-01` | Delete `O-ACCESS-EACH-DISTRICT` after compilation but before validation. | normative class remains; all 15 classes remain; source ID remains in source manifest. | independent expected-obligation set mismatch | `decisive_obligation_omitted` |
| `OM-02` | Modify source query/filter so `JA-ORD-01` is not returned. | query executes successfully; result set nonempty. | required-source manifest and query-result hash mismatch | `required_source_not_searched` |
| `OM-03` | Mis-scope `JA-ORD-01` to `J-BETA`. | source bytes/hash unchanged. | independent applicability oracle | `obligation_scope_misclassified` |
| `OM-04` | Mark accessibility obligation `not_applicable_data_only`. | valid enum value and record shape preserved. | semantic family/status compatibility rule | `invalid_not_applicable_conversion` |
| `OM-05` | Deduplicate accessibility and disparity obligations as “same normative obligation.” | one normative row and class-level totality remain. | semantic fingerprints and source-rule identities | `distinct_obligations_collapsed` |
| `OM-06` | Use a snapshot before `JA-ORD-01` became effective while declaring the later cutoff. | source resolver succeeds. | source-effect/knowledge-cutoff consistency | `snapshot_cutoff_mismatch` |
| `OM-07` | Exclude `JA-ORD-01` without a competent authorizer or materiality disposition. | exclusion field present and nonempty. | exclusion governance check | `unauthorized_material_exclusion` |
| `OM-08` | Traverse only top-level source objects, skipping a nested exception that creates an obligation. | source hash and top-level count remain. | generic recursive traversal mutation | `nested_obligation_path_skipped` |
| `OM-09` | Map an unavailable required source to an empty successful result. | no transport error. | availability/provenance distinction | `unavailable_source_laundered_as_empty` |
| `OM-10` | Reuse `D-GOOD` envelope after expanding scope to a new district. | candidate content mostly unchanged. | scope-hash and envelope-identity check | `scope_expansion_without_reassessment` |

`OM-01` is the mandatory decisive-obligation removal probe. It passes only if the entire protected
claim turns red while superficial denominator/marker checks can remain green.

### 5.2 Validator faults

| ID | Mutation | Required negative witness | Required red reason |
| --- | --- | --- | --- |
| `VM-01` | Accessibility validator returns `satisfied` unconditionally. | `D-MISSING-ACCESS` | `validator_always_true` |
| `VM-02` | Validator inverts `failed` and `satisfied`. | one known positive and one known negative | `validator_result_inverted` |
| `VM-03` | Validator converts unresolved venue evidence to satisfied. | venue evidence ref intentionally absent/unresolvable | `unknown_laundered_as_satisfied` |
| `VM-04` | Validator checks presence of the word “accessible,” not district-level verified evidence. | generic statement present; district 3 evidence absent | `form_based_validator` |
| `VM-05` | Validator trusts candidate self-attestation as owner evidence. | candidate supplies owner-like text without owner signature | `candidate_authority_laundering` |
| `VM-06` | Validator uses a superseded rule version that predates every-district coverage. | current source corpus plus stale rule hash | `validator_rule_version_stale` |
| `VM-07` | Independent checker imports and calls the same mutated primary validator. | shared component declared | `independent_check_common_mode` |
| `VM-08` | Validator skips the last district because of loop-bound fault. | at least four districts, violation in final one | `validator_iteration_incomplete` |
| `VM-09` | Validator ignores contradictory facility-owner evidence. | positive and revocation records both present | `contradictory_evidence_ignored` |
| `VM-10` | Validator governance record remains current after implementation hash changes. | validator byte/hash mutation | `unreviewed_validator_change` |

`VM-01` or an equivalent semantic fault is the mandatory validator-fault probe. It passes only
if the δ proof turns red even when the primary validator emits a superficially valid satisfied
record.

### 5.3 Governance, time, and projection faults

| ID | Mutation | Required result |
| --- | --- | --- |
| `GT-01` | Expire the measurement source/validator review while retaining green substantive outputs. | coverage becomes `open_world_unresolved` or `scope_insufficient`; promotion false. |
| `GT-02` | Set producer and independent reviewer to the same conflicted owner without disclosure. | independence unresolved; no `bounded_complete`. |
| `GT-03` | Accept a material post-publication challenge but do not suspend the public claim. | lifecycle/property test fails; proof red; reissue required. |
| `GT-04` | Silently rewrite the old envelope to include the newly discovered obligation. | append-only/history test fails. |
| `GT-05` | Render “risk ≤ δ” without the declared-set rider, unknown remainder, or expiry. | public projection benchmark fails even if backend receipt is correct. |
| `GT-06` | Reissue with unchanged envelope/receipt identity despite changed source set. | identity/content-binding test fails. |
| `GT-07` | A transported challenge event sets `withdrawn` without canonical claim-owner decision. | no-authority-by-transport invariant fails. |
| `GT-08` | Historical replay at `t0` uses current source/validator versions. | replay isolation test fails. |

## 6. Metamorphic laws

The benchmark generator should produce variants rather than teach the implementation only the
named examples. Each law includes an expected relation between runs.

| ID | Transformation | Required invariant or monotonic relation |
| --- | --- | --- |
| `ML-01` | Reorder source entries without changing semantic content. | Obligation set and decision are invariant; canonical hash is invariant if canonical ordering is specified. |
| `ML-02` | Duplicate the same source snapshot/obligation evidence. | Confidence and authority do not increase; dedupe is explicit and idempotent. |
| `ML-03` | Add a new applicable unsatisfied decisive obligation. | Authority status cannot improve; promotion becomes/remains false. |
| `ML-04` | Remove an applicable decisive obligation from the compiled set while source remains. | Coverage proof turns red; deletion cannot preserve a green current claim. |
| `ML-05` | Add an irrelevant out-of-scope source. | Substantive result does not change; source handling remains auditable. |
| `ML-06` | Expand jurisdiction/population/time scope. | Old envelope cannot be reused; fresh search/review is required. |
| `ML-07` | Narrow scope. | Any improved result requires a new scope identity/envelope; no silent mutation. |
| `ML-08` | Advance time beyond the earliest decisive TTL without new evidence. | Result can stay same or degrade, never upgrade; current use is blocked. |
| `ML-09` | Apply a semantic-preserving validator refactor with a reviewed new hash. | Validation outcomes remain equivalent across the fixture battery. |
| `ML-10` | Replace an authoritative source with an unverified mirror carrying identical bytes. | Content equality does not preserve authority validity; result degrades until source standing is verified. |
| `ML-11` | Discover a missed obligation after publication. | Historical `t0` replay is byte/result stable; current projection suspends and reissue opens. |
| `ML-12` | Insert mutually conflicting applicable obligations. | No collapse to satisfied; conflict remains explicit and routes to existing unknown/failed/scope status. |
| `ML-13` | Remove the competent obligation owner while keeping rule text. | No bounded current result where owner/mandate is decisive. |
| `ML-14` | Replace verified evidence with candidate self-description of the same proposition. | Candidate firewall prevents authority upgrade. |
| `ML-15` | Remove only the public conditional rider while retaining backend fields. | Projection test fails; public claim cannot remain green. |
| `ML-16` | Change only formatting/serialization of semantically identical source content under a canonical normalization rule. | Semantic obligation set is invariant; raw-source provenance still records the new bytes/version. |

Mutation adequacy and these metamorphic laws are relative to the declared fault model. Killing all
operators is not proof that every possible obligation or implementation fault is represented.

## 7. Required edge-case fixtures

### `F-01` — Happy path

**Input.** `D-GOOD`; all seven sources current, verified, admitted; independent review and
validator governance current; no open material defeater.

**Expected.** `bounded_complete` relative to the synthetic closure basis. No coverage-specific
blocker. Every substantive obligation independently satisfied. Fixture-only promotion may be
true. Public projection retains declared-set rider, unknown remainder, sources, and expiry.

**Adversarial check.** Remove the rider while all backend facts stay green: public benchmark must
fail.

### `F-02` — Decisive obligation missing

**Input.** `D-MISSING-ACCESS`; run `OM-01` so the decisive obligation instance is deleted while
another normative instance preserves the coarse class.

**Expected.** Independent source-to-obligation oracle detects mismatch;
`known_incomplete`; existing `failed` or `scope_insufficient` as appropriate; promotion false;
conditional proof red with `decisive_obligation_omitted`.

**Unsafe conclusion rejected.** “All 15 classes are present, so obligation completeness holds.”

### `F-03` — Late-discovered obligation after publication

**Input.** Publish `D-GOOD` under corpus version 1. At `t1`, admit a challenge showing a synthetic
newly discovered but already-applicable source rule at `t0` requiring backup-power verification,
which was absent.

**Expected.** Original envelope/receipt remains immutable and replayable at `t0`; current claim
moves to challenged/suspended; `known_incomplete`; proof red; perturbation and reissue required;
public correction links old and new records.

**Unsafe conclusion rejected.** “The old arithmetic is unchanged, so the public green claim may
stay current.”

### `F-04` — Validator later found unsound

**Input.** A validator used by `F-01` is later shown by `VM-08` to skip the final district.

**Expected.** Validator governance becomes `known_unsound`/suspended; every affected envelope is
located; current use suspended; `known_incomplete`; proof red for `validator_soundness`; reperform
with corrected/independent validator before reissue.

**Unsafe conclusion rejected.** “The receipt was signed before the bug was found, so it remains
valid for current authority.”

### `F-05` — Two obligations conflict

**Input.** Add synthetic source `JA-ORD-08` requiring district 3 venue closure for a contamination
order during the same effective interval, while `JA-ORD-01` requires an accessible open venue.

**Expected.** Both obligations remain represented. Conflict is explicit; no dedupe or silent
priority. Outcome maps to `unknown`, `failed`, or `scope_insufficient` according to a competent
conflict-resolution rule; absent such owner/rule, promotion false and coverage cannot be used to
claim satisfaction.

**Unsafe conclusion rejected.** “Both obligations were discovered, therefore the design is
complete and promotable.”

### `F-06` — Obligation owner unavailable

**Input.** Capacity obligation exists, but the named facility owner cannot be verified or has no
current mandate.

**Expected.** Source/owner entry `unavailable` or competence unresolved; coverage assessment
`open_world_unresolved` or `known_incomplete` if the required owner is a known missing item;
existing `scope_insufficient`; candidate analysis may continue with limitation; protected
promotion false.

**Unsafe conclusion rejected.** “No negative response was received, so the obligation is
satisfied.”

### `F-07` — Degraded mode

**Input.** Nondecisive public explanatory source is temporarily unavailable; all decisive source
families remain current. The declared stopping rule expressly permits a limited reviewer-only
candidate output but not a public promotion.

**Expected.** Degraded mode is purpose-scoped. Candidate/reviewer projection may proceed with a
typed limitation; public protected action remains blocked if the missing source is required for
that audience. No global `bounded_complete` is copied across purposes.

**Unsafe conclusion rejected.** “Degraded mode is a system-wide bypass.”

### `F-08` — Partial success

**Input.** Districts 1–2 satisfy all obligations; district 3 remains unknown. Scope is `all
residents/all districts`.

**Expected.** Whole-scope claim is not promoted. A separately identified narrower district 1–2
candidate may receive a new envelope if scope narrowing is legitimate and independently
reviewed. No slicing by UI or silent denominator change.

**Unsafe conclusion rejected.** “Two of three districts passed, so the aggregate is mostly
complete.”

### `F-09` — Rollback

**Input.** `F-03` material challenge accepted; public claim currently displayed.

**Expected.** PolicyOS stops current use, appends suspension/correction, emits external evidence
to the competent implementation owner, and opens reissue. It does not erase the old record or
execute facility/service rollback itself.

**Unsafe conclusion rejected.** “Rollback means delete the old receipt” or “PolicyOS reverses the
municipal operation.”

### `F-10` — Historical replay at declared cutoff

**Input.** Query the claim as known/admitted/published at `t0`, after `F-03` has produced a new
envelope at `t2`.

**Expected.** Replay resolves the old source snapshots, rule/validator versions, coverage
assessment, and publication; it also exposes later correction lineage without contaminating the
`t0` computation. A current query resolves the replacement/suspension.

**Unsafe conclusion rejected.** “Replaying history with today's obligation set is equivalent.”

### Additional adversarial fixtures

| ID | Condition | Expected outcome |
| --- | --- | --- |
| `F-11` | Required source query silently paginates only first page | `known_incomplete` or unresolved; proof red. |
| `F-12` | Same rule appears in two sources with different effective dates | preserve both provenance/time roles; no blind dedupe. |
| `F-13` | Source bytes identical but competent authority revokes the instrument | current authority degrades despite content equality. |
| `F-14` | Challenge evidence is cryptographically valid but outside scope | reject out-of-scope with preserved record; no claim reaction. |
| `F-15` | Material challenge cannot be resolved by deadline | suspended; materially inconclusive is not a pass. |
| `F-16` | Validator benchmark passes but independent checker has expired governance | no bounded current envelope. |
| `F-17` | Public projection hides a material exclusion due to audience compression | projection fails; backend truth cannot be compressed into false confidence. |
| `F-18` | One source family has no canonical owner in the repository | explicit owner gap; consolidation required; no research-created owner. |

## 8. Implementation-neutral fixture package

Another agent should be able to implement the benchmark with this logical package; filenames are
illustrative and not a package-placement decision.

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
  scope-and-cutoffs.yaml
  expected-obligation-oracle.yaml
  expected-source-to-obligation-derivations.yaml
  candidate-D-GOOD.yaml
  candidate-D-MISSING-ACCESS.yaml
  validator-expected-results.yaml
  mutation-manifest.yaml
  metamorphic-law-manifest.yaml
  expected-propagation.yaml
  public-projection-expectations.yaml
  history-replay-expectations.yaml
  independence-declaration.yaml
```

Every manifest and source is hash-bound in a pre-run fixture root. The benchmark runner records:

- implementation commit and configuration;
- rule/compiler/validator/governance versions and hashes;
- source snapshot and query hashes;
- mutation ID and injection point;
- primary result;
- independent oracle result;
- coverage assessment and existing-lattice effect;
- promotion result;
- conditional-proof usability;
- lifecycle/public projection result;
- historical replay result; and
- operator survival/equivalence disposition.

## 9. Execution protocol

1. **Freeze.** Freeze corpus, scope, expected oracle, mutation manifest, and evaluator version.
2. **Baseline positive.** Run `F-01`; verify the complete capability chain and conditional public
   rider.
3. **Baseline negative.** Run unmutated `D-MISSING-ACCESS`; verify the decisive obligation fails.
4. **Obligation mutation.** Run `OM-01`; require the independent oracle to detect omission and the
   protected claim to turn red despite a total coarse denominator.
5. **Validator mutation.** Run `VM-01` and `VM-04`; require independent fault detection and red
   propagation.
6. **Common-mode probe.** Run `VM-07`; require the independence mechanism to reject same-path
   validation.
7. **Metamorphic battery.** Execute `ML-01`–`ML-16`, generating domain/source/scope variants.
8. **Lifecycle battery.** Execute `F-03`, `F-04`, `F-09`, and `F-10`; verify append-only
   suspension/reissue/history semantics.
9. **Edge battery.** Execute the remaining fixtures and record exact existing-lattice outcomes.
10. **Independent scoring.** A scorer outside the implementation owner signs the result and
    surviving-material-mutant ledger.

## 10. Acceptance and kill rules

### Benchmark acceptance signal

A later implementation may claim this benchmark passed only when:

- every mandatory fixture has a content-bound result;
- `OM-01` and `VM-01` turn the full protected claim red;
- no material mutation survives without an independently accepted equivalent-mutant rationale;
- no checker relies solely on marker/shape/string presence;
- common-mode dependencies are disclosed and at least one common-mode mutation is detected;
- every incomplete coverage result maps into the one existing status lattice;
- promotion is false for every affected protected action;
- public projection removes/suspends the green δ chip and preserves the relative rider;
- late discovery and validator incidents produce append-only suspension/reissue, not silent edit;
- historical replay at the declared cutoff remains reproducible; and
- the independent oracle/scoring owner and governance are current.

### Immediate benchmark kill rules

The benchmark is invalid—not merely failed—if:

- expected results are generated by the implementation under test;
- source-to-obligation coverage is compared only at the 15-class enum level;
- the decisive omission mutation also removes the source, so the test cannot distinguish
  discovery from validation;
- the red result does not block the same protected action/public claim;
- a missing/expired oracle is treated as green;
- mutation operators or expected results are changed after seeing outcomes without a new frozen
  benchmark version;
- old envelopes are edited in place to make lifecycle tests pass; or
- benchmark passage is represented as proof of global obligation completeness.

## 11. Evidence this benchmark can and cannot support

If implemented and independently passed, the benchmark can support:

- the implementation detects the declared decisive-obligation omission and validator fault
  models;
- relative source-to-obligation coverage is behaviorally connected to promotion and public
  claims;
- current lifecycle reaction and historical replay satisfy the declared fixture properties; and
- the coverage mechanism is not merely a marker or class-enum check for these faults.

It cannot support:

- that the mutation operator set is exhaustive;
- that every legal/normative/measurement/implementation obligation is discoverable;
- that a real jurisdiction's closure basis is legally complete;
- that every validator is sound outside the fixture domain;
- that PolicyOS is legally compliant or authorized; or
- that the open-world remainder is empty or has probability below δ.

No benchmark was run in this research pass. The current status remains `semantic_test_missing`
until a later implementation and independent scoring record exist.
