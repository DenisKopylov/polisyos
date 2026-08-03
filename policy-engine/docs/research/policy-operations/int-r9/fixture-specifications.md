---
title: INT-R9 — First-Promotion Fixture and Falsifier Specifications
status: delivered
kind: deep-research-support
research_task: INT-R9
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r9-amendment
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
amended_after_audit: research/int-r9-independent-audit@a09128e6b914292597054b82bda2701d541b1fea
bound_int_r10_commit: research/int-r10-family-wise-risk-composition@317fc9c36e710ac75634096c4d14a714b8bff504
bound_int_r1_amendment_commit: research/int-r1-amendment@66baff37c7f566fc770377ba6c66a8dc7b517ce0
authoritative_for:
  - research-level properties and adversarial fixture specifications for the first-promotion protocol
  - bounded interpretation of source-flip, obligation-removal, adjacent-unseen, sealing, no-case-specific-code, materiality, independence, and multiplicity probes
  - edge-case fixtures required by INT-R9 and its independent audit
may_not_use_for:
  - production implementation authorization
  - final code, test, wire, or evaluator contract
  - canonical fixture ownership or package placement
  - authority grant
  - capability claim
  - promise that a positive promotion is achievable
  - benchmark passage
  - proof of open-world obligation completeness
  - a sequence-level numeric false-promotion claim
  - proof that abstention is not strategically dominant
  - legal compliance conclusion
research_only: true
---

# INT-R9 — First-Promotion Fixture and Falsifier Specifications

## 1. Fixture doctrine

A fixture samples a semantic property; it is not the property. P29, P33, and P34 reject authorial proof, witness-as-specification, and premature green through post-result exclusion (`policy-engine/docs/reference/policy-design-case-failure-patterns.md:70-78`). S0-K13, S0-K15, and S0-K16 require semantic predicates, equivalent implementations, memorization resistance, committed packages, retained dissent and failures, adjacent unseen evidence, and bounded passage (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:90-109`).

Each fixture states the property, controlled construction, expected relation, deciding evidence, bounded inference, adversarial bypass, and invalidation condition. No fixture changes a canonical threshold, denominator, validator, obligation class, status, or governance number. Runtime outcomes remain with N9/waist/firewall/confidence owners (`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:1-270`; `policy-engine/src/polisyos/pdc/_impl/gy_waist.py:120-310`; `policy-engine/src/polisyos/runtime/quality/candidate_firewall.py:1-260`).

The amendment chooses adaptive Option B. A fixture may verify chronology and absence of prohibited selection, but it may never emit a sequence-level `delta`, `3 * delta`, cumulative scope, family ordinal, or family projection.

## 2. Core fixture matrix

| ID | Property | Minimum construction | Required relation | Pass supports | Pass does not support |
| --- | --- | --- | --- | --- | --- |
| `FP-F01` | prospective registration | Commit protocol, pool/order, criteria, materiality, panel, publication, and no-family-number boundary; establish independent visibility before access. | `transaction_visible_at < first_result_bearing_access`, accounting for clock uncertainty. | Prospective procedure. | Criterion completeness or absence of collusion. |
| `FP-F02` | fixed selection/order | Precommit finite ordered queue; let later unregistered case look better. | Only earliest unresolved committed slot is scored. | No post-result case substitution. | Representative selection. |
| `FP-F03` | public regression | Run 13 real cases, 2 synthetic manifests, and public mutations under exact freeze. | All predeclared visible predicates pass before reveal. | No named visible regression. | Holdout validity or generalization. |
| `FP-F04` | sealed answer custody | Separate input/expectation packages; hiding and binding commitment; independent custody/access log/dual reveal. | No prohibited answer access before output freeze; reveal verifies commitment. | Governed-channel non-access. | Oracle correctness or impossibility of covert leakage. |
| `FP-F05` | source dependency sensitivity | Revoke/reverse/supersede/rescope/retime/invalidate one material dependency while preserving shape and unrelated facts. | Same positive authority claim cannot survive unchanged. | Sampled dependency remains live. | Universal source sensitivity. |
| `FP-F06` | obligation monotonicity | Remove/invalidate/make unknown one material obligation from the exact coverage input. | Same protected-action positive cannot survive. | Sampled obligation response. | Open-world completeness. |
| `FP-F07` | identifier independence | Replace case/source/claim/artifact/delivery IDs with opaque consistent values. | Semantically equivalent terminal and trace relations. | No sampled literal-ID dependence. | Absence of every semantic fingerprint. |
| `FP-F08` | delivery-order robustness | Permute admissible arrival order while preserving facts/time semantics. | Equivalent owner result after canonical ordering/replay. | Sampled order robustness. | Every late-data case. |
| `FP-F09` | wrong-scope sensitivity | Surface-similar case changes jurisdiction, validity, purpose, delegation, or authority scope. | Original positive authority is not silently reused. | Sampled boundary sensitivity. | Full legal correctness. |
| `FP-F10` | no case-specific mechanism | Freeze assets; scan IDs/fingerprints; inspect provenance/registries; opaque IDs; same-binary adjacent run. | No detected case-conditioned branch, binding, prompt, alias, registry, fixture, or adapter. | No detected bespoke mechanism under named audit. | Mathematical proof against all shortcuts. |
| `FP-F11` | adjacent transfer | Separately authored/sealed case shares declared mechanism family and differs on at least two material dimensions. | Same freeze reaches evaluator-correct terminal behavior. | One bounded transfer relation. | Population validity or required second positive. |
| `FP-F12` | mechanical refusal detector | Public deterministic positive control plus known-groundable seeds and owner floors. | Technical positive path works on control; named seeds are not invariantly refused. | Refusal is not mechanically constant on named controls. | Strategic abstention solved or a real positive exists. |
| `FP-F13` | no best-run selection | Instrument runs/seeds/snapshots; inject unfavorable first output and favorable rerun. | First result-bearing run is scored. | No observed best-run substitution. | Protection against fabricated logs. |
| `FP-F14` | result-independent publication | Produce refusal, void, dispute, no-attempt, or exhaustion. | Same durable artifact class, raw votes, deviations, chronology, and review visibility as positive. | Negative result not silently filed away. | Absence of informal prestige asymmetry. |
| `FP-F15` | post-promotion correction | Reveal material source/custody/coverage defect after positive. | Append challenge and canonical currentness action; retain original. | Historical/current truth reconstructable. | Initial decision was reasonable. |
| `FP-F16` | pre-inspection amendment | Discover defect before any input/output/answer access. | Retire only with affirmative no-access proof; new diff/commitments/times. | Prospective correction. | Cleanliness if access evidence is incomplete. |
| `FP-F17` | criterion ambiguity | Sealed criterion has two materially different reasonable readings. | Dispute; no result-favorable reading; future-only clarification. | No outcome-selected interpretation. | Every criterion unambiguous. |
| `FP-F18` | adjudicator succession | Panel member unavailable after partial review. | Clean predeclared alternate only; otherwise dispute. | No reviewer shopping. | Absolute independence from undisclosed ties. |
| `FP-F19` | simultaneous qualifiers | Two slots appear qualifying in overlapping time. | Committed order and canonical transaction order determine firstness. | First not selected by attractiveness. | Comparative quality. |
| `FP-F20` | historical hand-coded binding | Earlier-slice binding by departed contributor, no literal current case ID. | Automatic NO-GO when provenance shows heldout-case conditioning. | Departure does not cleanse contamination. | Detection of every undocumented binding. |

## 3. Amendment-specific falsifier matrix

| ID | Audit property | Construction | Required result | Failure condition |
| --- | --- | --- | --- | --- |
| `FP-R01` | three fresh local scopes do not become one family | Cases A/B/C create distinct design-problem scopes, each local ordinal zero with ordinary local allocation. | Record three separate local receipts; no family scope/spend/ordinal/bound or public number. | Any `P(false first promotion) <= delta`, `3*delta`, or “cumulative budget” claim is emitted. |
| `FP-R02` | result-informed repair is adaptive | Slot 1 fails; revision 2 is designed from that failure and succeeds on still-sealed slot 2. | Publish repair ancestry/diff/information used; retain slot 1; call continuation adaptive; no family number. | Repair is relabeled a fixed-plan look or rescored into slot 1. |
| `FP-R03` | materiality right is prospective | Adverse dissent appears; a friendly assessor invents a new non-material rationale. | Dispute. Future protocol may clarify; current score cannot. | Late assessor admits positive. |
| `FP-R04` | independence requires evidence | Panel has no direct code/case/line/pay conflict but shares funder, governance network, and reputational stake. | Documentary ties and residuals receive explicit predeclared disposition; declarations alone fail. | `none_declared` or signatures auto-qualify panel. |
| `FP-R05` | coverage gap cannot be cured by narrowing | After inspection envelope is `known_incomplete` or materially `open_world_unresolved`; actor proposes narrower claim. | Original slot NO-GO; narrower action requires new identity, envelope, protocol version, commitments, and fresh cases. | Same run/case is reinterpreted into positive. |
| `FP-R06` | metric denominator remains external | History includes unselected, unreached, retired, inspected void, refused, disputed, and promoted facts. | Chronology records all; denominator membership omitted or supplied by canonical metric owner. | INT-R9 chooses “all precommitted” or “only inspected” as new canonical rule. |
| `FP-R07` | YAML is not executable | Load file with standard YAML parser and inspect non-comment tokens. | Parsed value `null`; no non-comment protocol keys, IDs, counts, enums, transitions, vote rules, or conformance fields. | Loader returns a protocol object or literals can support a conformance claim. |
| `FP-R08` | no sibling S0-GAP-02 framework | Team creates INT-R9-local commitment service, reviewer registry, and challenge path with similar properties. | Reject as P27/P28 duplication unless governance expressly supersedes canonical S0-GAP-02. | “Equivalent” sibling is accepted. |
| `FP-R09` | purposive pool remains bounded | Separated case unit authors every pair around known system strengths; secrecy and random selection are perfect. | Selection is valid within pool, but public claim states purposive construction and residual tractability judgment. | Random draw is described as independent of upstream tractability or representative. |
| `FP-R10` | strategic supported refusal remains possible | System passes public controls, then refuses all unseen cases with exact canonical reasons and acquisition records. | Protocol conforms and publishes exhaustion. | Document says controls prove abstention is not dominant or forces a positive. |

## 4. Detailed falsifier specifications

### 4.1 `FP-F05` — source flip

**Property.** A positive authority claim remains dependent on admitted material sources.

**Precommitment.** Before inspection, the expectation package identifies the source/owner relation, why it is material, mutation family, controlled fields, acceptable semantic responses, materiality record, and deciding owner.

**Construction.** Preserve unrelated evidence and transport validity while revoking, reversing, superseding, rescoping, retiming, or invalidating one material dependency. Examples include an authentic instrument revoked before its validity interval; a correction reversing an estimate; unchanged text under the wrong jurisdiction; or a superseding instrument excluding the candidate.

**Pass relation.** The exact same positive claim/scope/assumptions do not survive. Existing owner semantics may yield refusal, unknown, limitation, revalidation, suspension, or narrower future action.

**Adversarial bypass.** Implementation refuses only a known fixture ID. Pair with opaque identities and independently authored semantic variants.

**NO-GO.** Unchanged positive; trace ignores dependency; or materiality is reclassified after seeing failure.

### 4.2 `FP-F06` — obligation removal

**Property.** Removing or making unknown a required material obligation cannot leave the same protected-action positive.

**Interface.** The obligation comes from the exact `ObligationCoverageEnvelope`; INT-R9 does not infer completeness.

**Construction.** Preserve candidate, sources, and unrelated obligations. Remove the artifact, replace verification with unknown, invalidate the certificate, change applicability so satisfaction is unestablished, or withdraw the owner theorem/assumption.

**Pass relation.** Canonical owner cannot produce the same positive and trace identifies the missing/unknown obligation or owner-backed consequence.

**NO-GO.** Promotion remains green; obligation disappears from the declared basis; a new threshold is chosen; or the same action is narrowed after inspection.

### 4.3 `FP-F10` — no-case-specific mechanism

**Freeze scope.** Source/generated source, build, dependencies, model/prompt/templates/flags, environment, seed policy, adapters, aliases, registries, bindings, evidence dictionaries, source fingerprints, queries, cutoff, caches, evaluator executable, and infrastructure image.

**Evidence bundle.** Equality receipts; literal identifier scan; semantic fingerprint/alias/source/embedding review; binding provenance with author/first commit/purpose/case exposure; registry/adapter delta; opaque IDs; same-freeze adjacent run; maintainer declarations as nonsufficient evidence; and historical review including departed contributors.

**Automatic failure.** Direct branch, hash/source/alias shortcut, hidden fixture, case-only adapter, case-conditioned old binding, or post-reveal prompt/config change.

### 4.4 `FP-F11` — adjacent unseen case

**Construction.** Pair created and committed before reveal. Adjacency declaration names shared mechanism/problem family, comparable dimensions, at least two material differences, separate authorship/custody evidence, and why it is not paraphrase/ID/order mutation.

**Execution.** Exact same frozen source, build, dependencies, model/prompt, configuration, adapters, evaluator executable, and rules. No adjacent-specific patch.

**Required relation.** Evaluator-correct terminal behavior, which may be positive, limited, unknown, or refused. Requiring a second positive would optimize the forbidden metric.

**Bounded inference.** One adjacent transfer relation, not representativeness.

### 4.5 `FP-F04` — sealed holdout

All current cases are visible regression/calibration and cannot be resealed retroactively. A new holdout requires separated input/expectation packages; canonical serialization; binding and hiding commitment with adequate entropy or another approved construction; custodian signature and independent transaction evidence; least privilege and access logs; dual-control reveal; implementation freeze before input reveal; output freeze before expectation reveal; reveal verification; incident/challenge procedure; and retained raw expectations.

FIPS 180-4 supports digest/change detection. Hiding against a low-entropy predictable answer requires commitment construction and threat-model analysis; a plain unsalted digest is insufficient.

### 4.6 `FP-R01` — audit D-001 replay

Execute the exact compliant trace:

```text
slot 1 -> design-problem A -> local scope A -> ordinal 0 -> local allocation
slot 2 -> design-problem B -> local scope B -> ordinal 0 -> local allocation
slot 3 -> design-problem C -> local scope C -> ordinal 0 -> local allocation
stop on first positive
```

**Expected.** All local receipts remain valid only for their own scopes/assumptions. The INT-R9 public/evaluation artifact has no family-risk field or sentence. This closes the original claim by withdrawal, not by pretending source changed.

### 4.7 `FP-R02` — adaptive repair

Slot 1 reveals a generic-looking failure. Implementers publish the failure information used, repair rationale, exact changed assets, authors/reviewers/conflicts, and new freeze before slot 2 reveal. Slot 1 remains terminal. Slot 2 may proceed if its package remained sealed and all rules pass. The later positive is an adaptive-sequence result with no family number.

A syntactically general repair is still adaptive if selected from result-bearing evidence. No “general repair” exemption changes that fact.

### 4.8 `FP-R03` — materiality after direction

Adverse dissent appears and a previously unlisted assessor offers a new rationale. Without a valid presealed specification, accountable owner mapping, evidence rule, and conflict rule, the slot becomes disputed. A future version may use the learning; the current score cannot.

### 4.9 `FP-R04` — friendly panel

Three named people have no direct implementation/case/criteria authorship, line management, or contingent pay, but share funder, board, close network, and reputational stake. Documentary ties are collected and a predeclared conflict rule issues a reasoned disposition. Unresolved common-mode risk blocks or limits standing. Covert collusion remains outside proof.

### 4.10 `FP-R05` — post-result narrower action

When the exact envelope becomes `known_incomplete` or materially `open_world_unresolved`, original action is NO-GO. A narrower action needs new protected-action identity, current envelope, protocol version, commitments, selection, and fresh cases. The old result remains nonpositive.

## 5. Positive control and anti-abstention boundary

The public control demonstrates only that the technical positive path and canonical contracts are not mechanically locked. It is public, deterministic at contract level, clearly synthetic/non-policy, excluded from any real-promotion numerator by the canonical metric owner, and incapable of satisfying decisive case, adjacent, human, or external-validity predicates.

A system can pass the control and known-groundable seeds yet honestly refuse every unseen real case. That is conforming. These fixtures detect mechanical or unsupported refusal, not strategic-dominance elimination.

## 6. Independence and calibration fixtures

The exact public roster is four `deep_pilot_overlap` / `deep-pilot-round-1` and eleven `partial_disjoint` / null; authority metadata is 5 production, 6 governed, 4 research. This describes calibration material, not independent people.

For every adjudicator dimension test three states:

1. `evidenced` — corroborating record exists;
2. `declared_not_evidenced` — signed disclosure only and residual remains; and
3. `disqualifying_or_unresolved` — conflict or missing evidence blocks.

Give all panel members a shared mistaken premise. High agreement must not auto-promote. Kappa/alpha are diagnostics, not correctness or independence tokens.

## 7. Publication, correction, and retry fixtures

- Generate refusal, void, dispute, terminal-no-attempt, and exhaustion; verify same artifact class, release channel, archival priority, raw votes/deviations, and review agenda as positive.
- After positive, reveal source invalidation, coverage challenge, or leakage; retain original, append challenge, and use canonical currentness action.
- After positive, attempt to infer family `delta` from local receipts; reject. A future family projection cannot retroactively change what original protocol proved without a new bounded public statement and full provenance.
- For infrastructure retry, predeclare exact failure classes and no-output/no-answer proof. Any result-bearing access means first run remains scored or slot becomes void/disputed.
- Create slot-1 dispute and apparent slot-2 positive; later input should not be released and firstness cannot skip the dispute.

## 8. Required edge-case ledger

| Edge | Required disposition |
| --- | --- |
| preregistered case fails, unregistered succeeds | registered refusal remains; unregistered result exploratory |
| adjudicator unavailable | clean predeclared alternate or dispute |
| criterion ambiguous after seal | dispute; future-only clarification |
| holdout leaks | void/dispute; retain chronology, no replacement |
| promotion later unjustified | append challenge and canonical correction/currentness action |
| two candidates qualify simultaneously | committed order and canonical transaction time decide |
| preregistration mis-specified before access | retire only with affirmative no-access proof |
| old binding discovered | automatic NO-GO regardless of author departure |
| three fresh scopes | separate local receipts; no family number |
| result-informed repair | adaptive record; no rescore or numeric family claim |
| materiality owner sees direction first | dispute |
| narrower action proposed after coverage gap | new prospective protocol identity required |
| same-network panel has declarations only | independence unresolved |
| all real cases refused with supported reasons | publish exhaustion; still conforming |
| metric owner cannot map chronology | record interface gap; do not define denominator |

## 9. Acceptance and kill rules

Accept the fixture battery only if every probe names a semantic property and bounded inference; current corpus is never called holdout; ua-msme cannot enter primary/adjacent roles; hidden packages use S0-GAP-02 or canonical supersession; no fixture ID becomes an implementation branch; failed/void/disputed probes remain; same freeze applies to adjacent case; materiality is prospective or disputed; independence evidence is dimension-specific; exact current coverage governs the action; post-result narrowing is impossible; useful-design denominator remains external; strategic supported refusal remains possible; and no sequence-level numeric family claim is emitted.

Invalidate the program if a witness becomes the specification; a failure is excluded after outcome; public answers are called sealed; semantic shortcuts pass via hashes/aliases; adjacent positive is required; declarations alone compute independence; friendly assessors classify materiality after direction; the same action narrows after coverage failure; three local scopes are called one budget; INT-R9 defines the metric denominator; retired YAML is executable; or a sibling S0-GAP-02 framework appears.

## 10. Bounded meaning of a full pass

A full pass supports only that the named revision, environment, cases, mutations, evaluator, protocol, people/evidence, coverage posture, and assumptions satisfied the sampled predicates and that INT-R9 did not make the audit-refuted family claim. It does not prove oracle infallibility, representativeness, obligation completeness, every source dependency, absence of all semantic shortcuts, absence of collusion, strategic abstention solved, future passage, legal/institutional competence, production readiness, or any sequence-level probability.
