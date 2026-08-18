---
title: Wave 4 — ratification candidates
status: delivered_consolidation_candidates
kind: research_consolidation_ratification_candidates
research_scope: [OPS-R14, PAO-R36, PAO-R4, S0-GAP-02]
repository_branch: research/wave4-consolidation
orientation_commit: 610e485569da8b5b13afd767ae52b29d3f2c8e95
documentation_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
inspection_date: 2026-08-17
research_only: true
ratification_performed: false
candidate_count: 7
may_not_use_for:
  - claim that any candidate is ratified
  - production implementation authorization
  - package repair or mutation
  - final wire, schema, package, database, serialization, media type, or API contract
  - canonical owner, vendor, custodian, evaluator, signer, or institution appointment
  - authority grant
  - capability claim
  - permission to publish, sign, score, promote, or open a gate
  - claim that OPS-R15 is unblocked
  - automatic amendment of AGENTS.md, the pattern register, a plan, backlog, or system-design decision
---

# Wave 4 ratification candidates

## 1. Decision boundary

These are propositions a **subsequent ratification act** may accept, amend, defer, or reject. This document does not ratify them and does not change any package artifact.

Evidence is taken from both disjoint lines: the audit line establishes the defect; the response line and independent verification establish the terminal state. Where the architect ruled during the wave, the ruling is carried as a candidate with its falsifier and evidence, not silently converted into authority.

## 2. Candidate register

| Candidate | Proposition | Evidence class | Ratification effect if accepted |
| --- | --- | --- | --- |
| `W4-RC-01` | Census claims are holder-relative: consolidation may rely on its recomputation, while a package that did not execute the walk must label the same counts `institutionally_supplied`; a package cannot settle a zero by inheritance. | Complete controlled walk at `109ba3f44` with positive/negative controls; five live package attribution sites. | Register a mandatory executing-party/holder field for set-level census claims and preserve all six zeroes at consolidation level. |
| `W4-RC-02` | P37 retains exactly five fixed labels; S0-GAP-02's machine-observation, attestation, and institutional-acceptance distinctions become required sub-annotations, not additional labels. | Registered P37; S0 verifier crosswalk; conditional positive eligibility of `machine_observed`. | Preserve condition-free positive eligibility by fixed lookup while retaining all three distinctions. |
| `W4-RC-03` | Research standing, capability standing, and first-public-signature gate standing are separate mandatory axes. | OPS-R14 blocker and verified three-axis repair; PAO-R4 positive standing over absent capability; S0 verifier standing-shape observation. | Route the three exact fields to `AGENTS.md`; prohibit audit-verdict tokens from serving as aggregate standing. |
| `W4-RC-04` | `F-14A` is withdrawn; `F-14B` remains a governed result; no “strengthen F-14A” round may be commissioned. | OPS amendment verification `AV-B02`; remediation delta verification `NOT_CLOSED`; absent INT-R9 warrant; content comparison cannot establish provenance independence. | Remove the positive route from future adoption and register a genuinely disjoint-custody provenance record as the only condition for return. |
| `W4-RC-05` | Every repair that preserves a positive by adding a condition creates a new gate predicate that must itself be classified; closure occurs only when the condition is constructed at the level of the property it names. | Independent instances: `F-14A` and `machine_observed`; both recurse one level below P37 when the added condition is merely declared. | Register the rule beside P37 and require a falsify-the-condition probe. |
| `W4-RC-06` | `P38` must be registered canonically: a gate implemented against a proxy misclassifies exactly at the boundary it exists to police. | GY plan §3.5.14 and Atlas Execution Doctrine cite P38 with measured instances; `AGENTS.md` and the canonical pattern register stop at P37 at the pin. | Add P38 to `AGENTS.md` and the pattern register; until then cite it as an outstanding proposal, not a registered pattern. |
| `W4-RC-07` | No active research remains on the first-milestone path; remaining blockers are engineering wiring and institutional evidence, while later research items have conservative fail-closed alternatives. | Re-derived 27/21/19 agenda; PAO-R36 dependency map; absent/unallocated capability chains; explicit `not_established`/refusal/abstention terminals. | Permit planning to sequence engineering and institutional work without claiming implementation or suppressing later research. |

## 3. `W4-RC-01` — holder-relative census attribution

### Proposition

A census record must name:

1. the exact pin;
2. the path denominator;
3. the file-type denominator;
4. matching semantics;
5. the executing party;
6. the holder making the present claim; and
7. the P37 label relative to that holder.

The same numeric tuple may therefore be `recomputed` for consolidation and `institutionally_supplied` for a package. A zero is usable only by the holder that executed or independently reconciled a complete denominator.

### Evidence

The controlled walk at `109ba3f44` reproduced all thirteen commissioned tokens in both denominators, including six zeroes and the correction of `legal_hold` from the audit's incomplete `2/4/5` to `2/7/8`. Positive controls `may_not_use_for` and `supersede` were non-zero and matched prior complete-walk results; the negative control was zero.

Terminal package text still contains five attribution defects:

- PAO-R4 `orientation-ledger.md:149` and `:199`;
- PAO-R4 `amendment-delivery-readback.md:120`;
- PAO-R36 `amendment-ledger.md:58` and `:107`.

OPS-R14's equivalent language was removed after its verifier graded the issue blocking. PAO-R4's verifier acknowledged that it had not freshly recomputed the counts but left the same overclaim standing.

### Falsifier

Keep every number unchanged but replace the executing party with a holder whose environment cannot walk the complete tree. If the record still labels the result `recomputed` or lets that holder settle a zero, the rule failed.

### Non-effect

Acceptance would not edit the five package sites; it would authorize a later correction route. It would not convert token absence into semantic capability absence.

## 4. `W4-RC-02` — five labels with required sub-annotations

### Proposition

The registered label set remains:

`recomputed` · `independently_reconciled` · `consumer_asserted` · `institutionally_supplied` · `not_established`.

Required sub-annotations preserve three distinctions:

- deterministic recomputation versus bounded machine observation;
- consumer-specific assertion versus signed attestation by another constrained role; and
- premise supplied versus institutionally accepted for a named scope after competence, dissent, and challenge review.

### Evidence

S0-GAP-02's six-way vocabulary does not widen its stated non-positive set. Its verifier correctly commended the distinctions. The defect is lookup shape: `machine_observed` is positive-eligible only when it is either a subtype of recomputation or retained by a second non-producing observer; bare producer telemetry maps to `not_established`. A label whose positive eligibility depends on a declared condition recreates P37 one level down.

### Falsifier

Present a producer's green telemetry with a `machine_observed` marker but remove the independent observation or deterministic controlled-artifact derivation. If the gate remains positive because the label is present, the proposal is unsafe.

### Non-effect

Acceptance would not rewrite S0-GAP-02. It would define the canonical crosswalk for later implementation and documentation correction.

## 5. `W4-RC-03` — three-axis standing

### Proposition

Every research package that can be accepted while its capability or first-public-signature gate remains closed must report:

```yaml
research_standing: <research disposition>
capability_standing: <runtime capability disposition>
gate_standing: <first-public-signature gate disposition>
```

An audit verdict is not a standing value.

### Evidence

OPS-R14's audited `standing: NO_GO` collapsed a valid bounded research architecture into an operational refusal; its verified repair uses all three axes. PAO-R4 proves the converse failure: one `result_standing: GO_WITH_REVISIONS` publishes a positive while the same package has an unre-executed census, retained attribution overclaims, an `absent/unallocated` capability chain, and no canonical emission owner. S0-GAP-02's verifier separately observed that one field compresses research-technical and institutional/readiness propositions.

### Falsifier

Construct a package whose research contract is accepted, whose capability is absent, and whose publication gate is closed. If one field cannot express all three without publishing either a false positive or a false negative, the one-axis shape fails.

### Non-effect

Acceptance would route a governance rule to `AGENTS.md`; it would not upgrade or downgrade any current package standing by itself.

## 6. `W4-RC-04` — withdraw `F-14A`, preserve `F-14B`

### Proposition

`F-14A` is withdrawn because it measures the wrong property. Comparing instrument bytes, receipts, and substantive fields can establish content agreement, not whether the supposed authoritative record is independent of the successor whose claim it validates.

`F-14B` remains: with declarations and markers intact but the succession premise absent, contradictory, or merely supplied, the exact result is `succession_scope_not_established`.

A positive may return only after a genuinely disjoint-custody record constructs administration, derivation, storage, key-custody, failure, and observation independence.

### Evidence

The terminal delta verifier admitted an adversarial successor-controlled record that shares storage/root key or is derived from the successor's submission while every content comparison passes. The claimed INT-R9 warrant does not exist: `non-producing`, `admitted_instrument`, and `admitted=true` do not occur in that corpus; the nearest admission text says admission is not authority, and the nearest fixture demands absolute independence from undisclosed ties.

### Self-falsification requirement

A counter-claim that content comparison can establish provenance would be falsified by one successor-controlled record with identical bytes/receipts that passes the detector. That counterexample already exists in the delta verification.

### Non-effect

Withdrawal does not erase F-14B, the wider OPS-R14 architecture, or INT-K08 negative completion. No repair round is commissioned here.

## 7. `W4-RC-05` — conditions create predicates

### Proposition

> Every repair that preserves a positive by adding a condition creates a new gate predicate, which must itself be classified. There is no fixed point until the condition is constructed at the level of the property it names.

### Evidence

- `F-14A` added “independently reconciled non-producing authoritative record,” then trusted the record's non-producing character without reconstructing provenance.
- `machine_observed` added a frozen-scope/second-observer condition, then made positive eligibility depend on that declared condition rather than a fixed label lookup.

Both repairs move the unconstructed premise one level down while leaving the positive alive.

### Required closure signal

For each added condition:

1. assign one registered P37 label;
2. name the evidence source and non-producing observer;
3. construct the property rather than its marker; and
4. falsify the condition while keeping its declaration intact.

### Non-effect

This is a governance candidate, not a package-level defect reopening.

## 8. `W4-RC-06` — P38 registration deficit

### Proposition

P38 should be canonically registered as the proxy-gate pattern: the proxy agrees with the target property in ordinary cases and diverges exactly at the decision boundary.

### Evidence

The GY plan defines P38 in §3.5.14 and records measured examples including exit code used as completion, field name used as non-decisiveness, address used as identity, and mechanism-byte rounds used as proof of wrong design. The Atlas plan cites and applies the same pattern. At the documentation pin, both `AGENTS.md` and `policy-design-case-failure-patterns.md` stop at P37.

### Falsifier

For any proposed P38 instance, replace the proxy while holding the named property fixed, or change the property while holding the proxy fixed. If the gate tracks the property, it is not a P38 instance. If it tracks the proxy, it is.

### Non-effect

Until registration occurs, documents must say “P38 proposal” or “outstanding registration,” not “registered P38.”

## 9. `W4-RC-07` — first-milestone path contains no active research

### Proposition

The first-milestone path is blocked by engineering and institutional evidence, not by a missing theory result.

### Evidence

The typed agenda is exactly 27 engineering, 21 institutional, and 19 further-research items. Every further-research item has a conservative existing behavior: refusal, `not_established`, abstention, bounded claim, withheld specification assurance, or fail-closed multilingual parity. PAO-R36's explicit unresearched dependency, INT-R6, blocks an authoritative multilingual positive only; it is not required to issue a first-milestone result under a single admitted language posture. All complete capability chains remain `absent/unallocated`.

### Falsifier

Identify a first-milestone positive that cannot be produced or honestly refused without proving a new theorem or resolving one of the 19 later research questions. No such dependency was found. A future dependency graph that names one would refute this candidate.

### Non-effect

Acceptance would not declare implementation readiness. It would preserve the priority distinction: engineering wiring and named institutional commitments can remain blockers after research is complete.

## 10. Items explicitly not candidates

The following are already governed constraints or preservation findings, not new ratification candidates:

- F11 closes only through `RP-10 + RC-01 + RC-07 + F-04 + F-09 + DE-07`;
- the product outcome vocabulary remains three elements; `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED` is an INT-K08 negative completion, not a fourth;
- no accepted audit finding is reopened;
- no capability, owner, gate, or OPS-R15 unblock is promoted;
- `PAO-R36-I-001` remains declined on the correct 48/215/260 census;
- PAO-R4-III-001 remains narrowed to authority-to-determine, never executability; and
- S0-GAP-02's INT-K08 placement remains honored.