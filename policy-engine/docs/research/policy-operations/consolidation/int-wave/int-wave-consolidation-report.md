---
title: INT wave — Consolidation Report
status: delivered
kind: research-consolidation
research_scope: [INT-R1, INT-R9, INT-R10]
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-wave-consolidation
pinned_repository_commit: a548a2f939995ad81b4febe3402bdcb35ae11bad
inspection_date: 2026-08-03
research_only: true
consolidation_verdict: ratifiable_kernel_with_blocked_capabilities
int_r9_verification_standing: verified_pending
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, package, database, serialization, or API contract
  - canonical owner appointment
  - authority grant
  - capability claim
  - benchmark passage
  - automatic amendment of any authoritative backlog, plan, or system-design decision
  - legal compliance or institutional competence conclusion
  - permission to execute, promote, release, or publish a governed result
  - assertion that bounded_complete is currently issuable
  - assertion that a live family declaration, chronology verifier, aggregate projection, or reproduction chain exists
  - numeric family-wise claim for outcome-dependent repair
  - unconditional claim that all applicable obligations are known
  - change to the current obligation denominator, confidence scope identity, risk budget, status lattice, or canonical owner
---

# INT-R1 / INT-R9 / INT-R10 consolidation report

## Executive disposition

This wave supports a **small authority-band ratification kernel**, not a production capability claim.
The safe kernel is: obligation completeness is relative to a declared basis and language; every
numeric risk statement remains relative to its declared obligation set and maintained assumptions;
`bounded_complete` requires constructed rather than declared independence; several canonical
problem scopes may support one family statement only through prospectively enforced local bounds
and canonical family custody; per-problem scope identity must remain intact; and a first governed
promotion may carry a nonnumeric custody/anti-selection claim without carrying a sequence-level
risk claim.

The wave does **not** establish that PolicyOS can issue `bounded_complete`, emit a canonical family
bound, execute the INT-R9 protocol, supply an independent scorer, or validate outcome-dependent
repair numerically. Those remain blocked. Candidate work remains permitted under typed limitation;
only the affected authority claim fails closed, following the Stage-0 authority-band/candidate-band
rule (policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:164-212).

INT-R9 is **verified-pending** at the pinned commit. Its amendment is in `main`, but no separate
amendment-verification artifact is present. The original `NO_GO` therefore remains the last
independent verdict. This consolidation carries the amended Option-B nonnumeric protocol as a
pending repair position, not as verified conformance, and does not declare the three blocking
findings independently closed (policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:44-110; policy-engine/docs/research/policy-operations/int-r9/amendment-ledger.md:31-81; policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-independent-audit.md:31-82).

## 1. Baseline, denominator, and method

All repository claims in this consolidation are pinned to `a548a2f939995ad81b4febe3402bdcb35ae11bad`. The brief's denominator is
**40 substantive documents**. The reproducibility census below opens those forty documents and
also lists the separate INT-R10 revision disposition ledger as a supporting index, yielding **41
repository paths read**: 15 INT-R1 paths, 13 INT-R9 paths, and 13 INT-R10 paths. The supporting
ledger is not treated as an independent source of findings or as evidence for its own claims.

| Thread | File count | Complete path set |
| --- | ---: | --- |
| INT-R1 | 15 | `policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:1`<br>`policy-engine/docs/research/policy-operations/int-r1/amendment-ledger.md:1`<br>`policy-engine/docs/research/policy-operations/int-r1/artifact-and-state-machine-sketch.md:1`<br>`policy-engine/docs/research/policy-operations/int-r1/benchmark-and-edge-case-fixtures.md:1`<br>`policy-engine/docs/research/policy-operations/int-r1/external-primary-source-ledger.md:1`<br>`policy-engine/docs/research/policy-operations/int-r1/open-world-impossibility-and-relative-coverage.md:1`<br>`policy-engine/docs/research/policy-operations/int-r1/repository-census-and-anchor-ledger.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r1/int-r1-anchor-and-citation-verification.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r1/int-r1-claim-evidence-ledger.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r1/int-r1-formal-argument-audit.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r1/int-r1-independent-audit.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r1/int-r1-orientation-error-ledger.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r1/int-r1-recommended-revision.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r1/int-r1-amendment-conformance-ledger.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r1/int-r1-amendment-verification.md:1` |
| INT-R9 | 13 | `policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:1`<br>`policy-engine/docs/research/policy-operations/int-r9/amendment-ledger.md:1`<br>`policy-engine/docs/research/policy-operations/int-r9/contamination-census.md:1`<br>`policy-engine/docs/research/policy-operations/int-r9/first-promotion-evaluation-protocol.yaml:1`<br>`policy-engine/docs/research/policy-operations/int-r9/fixture-specifications.md:1`<br>`policy-engine/docs/research/policy-operations/int-r9/state-machine-and-artifact-contracts.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-adversarial-reading.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-anchor-and-citation-verification.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-claim-evidence-ledger.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-independent-audit.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-orientation-error-ledger.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-recommended-revision.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-seam-and-crosscheck.md:1` |
| INT-R10 | 13 | `policy-engine/docs/research/policy-operations/int-r10-family-wise-risk-composition.md:1`<br>`policy-engine/docs/research/policy-operations/int-r10/fixture-and-artifact-sketch.md:1`<br>`policy-engine/docs/research/policy-operations/int-r10/revision-ledger.md:1`<br>`policy-engine/docs/research/policy-operations/int-r10/source-and-transfer-ledger.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r10/int-r10-anchor-and-citation-verification.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r10/int-r10-claim-evidence-ledger.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r10/int-r10-formal-argument-audit.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r10/int-r10-independent-audit.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r10/int-r10-orientation-error-ledger.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r10/int-r10-recommended-revision.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r10/int-r10-specification-conformance.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r10/int-r10-revision-conformance-ledger.md:1`<br>`policy-engine/docs/research/policy-operations/audits/int-r10/int-r10-revision-verification.md:1` |

The consolidation followed the Stage-0 precedent: disagreement was adjudicated rather than
averaged; a theorem, protocol, design pattern, implementation convenience, repository gap, and
capability were kept distinct; and statements were considered ratifiable only when they bind the
authority band without forbidding candidate-band work (policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:43-116; policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:164-212).

Set-level statements were taken from complete finding registers and complete file/registry
censuses, not from one sampled member or frontmatter metadata. This matters because the wave's
orientation errors included a 14-versus-15 denominator, a three-versus-four calibration count, and
a five-profiles-versus-thirteen-instruments confusion (policy-engine/docs/research/policy-operations/audits/int-r1/int-r1-independent-audit.md:98-129;
policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-independent-audit.md:108-144;
policy-engine/docs/research/policy-operations/audits/int-r10/int-r10-independent-audit.md:118-153).

## 2. What the wave asked

INT-R1 asked what honest completeness can survive an open world. INT-R9 asked how the first
positive governed promotion can be recognized without post-result selection. INT-R10 asked how
false-promotion risk can compose across the canonical per-problem confidence scopes that INT-R9
actually reaches.

The three questions form one chain:

1. INT-R1 defines what each member's obligation basis and conditional risk statement can mean.
2. INT-R10 defines the fixed-family composition theorem and the exact pinned arithmetic envelope.
3. INT-R9 defines the custody of firstness, selection, chronology, adjudication, publication, and
   correction, then deliberately declines a numeric family claim because it keeps outcome-informed
   repair.

## 3. Adjudicated results

| Question | Position that won | Why it won | Position rejected or narrowed |
| --- | --- | --- | --- |
| Can finite search certify global obligation completeness? | Only conditionally, and only relative to a per-scope closure disposition; the positive result is conditional relative inclusion. | The indistinguishable unseen-extension construction survives audit, while the amendment explicitly leaves compiler completeness and validator soundness as assumptions (policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:300-432). | Any unconditional “all applicable obligations are known” claim. |
| Can PolicyOS issue `bounded_complete` now? | No. | The research specified independence but did not construct an independent producer/scorer/governance chain; verification confirmed the refusal (policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:35-101; policy-engine/docs/research/policy-operations/audits/int-r1/int-r1-amendment-verification.md:31-70). | Treating an `independence_record`, a second function name, or benchmark metadata as independence. |
| Did the original INT-R9 three-slot protocol have one cumulative delta budget? | No canonical family invariant existed. | N9 derives one scope per design problem, and the ledger is scope-local (policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-374; policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476). | Prose such as “cumulative,” “no reset,” or “one sequence” as a substitute for owner-enforced composition. |
| What survives for first promotion? | The amendment's pending Option-B position: adaptive continuation with no numeric family claim. | Current amended text keeps firstness, sealing, no substitution, adjudication, negative publication, and correction while attaching no probability to the selected positive; independent conformance is still pending (policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:44-110; policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-independent-audit.md:31-82). | Any `delta`, withdrawn multiple-of-delta figure, or other family-wise number for the current adaptive protocol. |
| Is fixed-family composition possible? | Yes, by Boole's inequality when valid prospective local bounds are enforced and sum to the declared family bound. | The theorem survived audit and revision verification; no common null, estimand, exchangeability, or independence is required in the union step (policy-engine/docs/research/policy-operations/int-r10-family-wise-risk-composition.md:420-515; policy-engine/docs/research/policy-operations/audits/int-r10/int-r10-revision-verification.md:160-450). | The claim that composition is mathematically impossible without weakening per-problem scope identity. |
| What is the pinned owner arithmetic? | One current-registry scope has an all-path envelope below `delta * schedule_mass * 3/20`; an exact three-scope mass-one family is below `(9/20) * delta`. | The revision and verifier enumerated the complete registry and reproduced the exact Basel coefficient and class weights (policy-engine/docs/research/policy-operations/int-r10-family-wise-risk-composition.md:36-103; policy-engine/docs/research/policy-operations/audits/int-r10/int-r10-revision-verification.md:160-450). | Root policy delta as an attainable member-event probability; the withdrawn arithmetic and equal-share prescription. |
| Does the runtime emit that family result? | No. | No canonical family declaration, chronology verifier, aggregate current-head projection, or public owner statement exists (policy-engine/docs/research/policy-operations/int-r10-family-wise-risk-composition.md:36-103; policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476). | Treating a derivable mathematical envelope, fixture, or research sketch as a live capability. |
| Does outcome-dependent repair have a numeric theorem? | Not in the live owner. | The repaired adaptive theorem states the required history-measurable/selection-valid premise, but no useful owner theorem satisfies it (policy-engine/docs/research/policy-operations/int-r10-family-wise-risk-composition.md:420-515; policy-engine/docs/research/policy-operations/audits/int-r10/int-r10-revision-verification.md:160-450). | “Anytime-valid” or predictable allocation as automatic validation of outcome-selected repair. |

## 4. What was established

### 4.1 INT-R1: bounded honesty, not world closure

The impossibility result is premise-relative: no finite trace certifies global completeness while
an observationally invisible decisive extension remains admissible. Every protected use therefore
needs one of `closed_by_competent_basis`, `open_under_unseen_extension`, or
`closure_not_established`; only the first defeats the premise for its exact boundary. The positive
theorem proves inclusion and checking relative to a declared basis and language under named
semantic assumptions. Governance, mutation, reperformance, and currentness support reliance; they
do not generate semantic truth (policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:35-101; policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:300-432).

The public probability statement must identify the declared obligation set and expose the basis,
scope, language/rule versions, exclusions, unknown remainder, cutoff, challenge state, and expiry.
It is not a probability that no obligation was omitted (policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:35-101; policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:39-52).

### 4.2 INT-R10: a theorem and a pinned envelope, not a projection

For reached-member events `V_i`, prospectively enforced valid local caps compose by the union
inequality. The theorem is heterogeneous: it does not require the members to share one null,
estimand, exchangeability assumption, or independence assumption. Coarse-information sharpness is
valid only after deliberately reducing the local owner to marginal statements `P(V_i | A_F) <= b_i`
(policy-engine/docs/research/policy-operations/int-r10-family-wise-risk-composition.md:420-515).

The exact current-source formula and complete expanded-class census give the narrower pinned
envelope. That envelope is a mathematical fact about the pinned code/registry under its assumptions.
It is not a runtime family certificate, observed spend, empirical estimate, or authority grant
(policy-engine/docs/research/policy-operations/int-r10-family-wise-risk-composition.md:36-103; policy-engine/docs/research/policy-operations/audits/int-r10/int-r10-revision-verification.md:160-450).

### 4.3 INT-R9: pending custody position without a risk claim

Subject to the outstanding conformance verification, the amended protocol is intended to govern the earliest qualifying attempt, pre-result commitments, case and
run substitution, implementation ancestry, human adjudication, disputes, negative terminals,
publication, and later correction. It may state that no prohibited substitution was found in the
governed record. It may not claim population performance, legal compliance, competence, production
readiness, complete obligation discovery, or sequence-level family risk control (policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:44-110).

`ua-msme-affordable-loans-2022` remains public regression material and is ineligible as decisive or
adjacent evidence. `exhausted_without_promotion`, refusal, dispute, and void remain valid primary
results; the protocol owes no positive result. These are the current amended-text positions, not a verified conformance verdict (policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:44-110; policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-independent-audit.md:31-82).

## 5. What was refuted

The following positions are not available for ratification or downstream reliance:

- global obligation completeness from a finite trace without a competent scoped closure premise;
- current `bounded_complete` issuance;
- a cumulative family budget created by prose over distinct canonical scopes;
- root policy delta as a member-event probability or ordinal-zero reservation;
- the withdrawn original INT-R10 source-sharpness and equal-share remedy;
- a live canonical family declaration/projection/reproduction chain;
- a numeric family theorem for INT-R9's outcome-dependent repair;
- a fixture, schema-shaped sketch, frontmatter line, or self-authored ledger as its own authority;
- secrecy or within-pool randomization as proof of pool-level independence; and
- any promotion, compliance, efficacy, competence, or production claim inferred from these research
  artifacts.

## 6. What remains blocked

| Block | Classification | Current owner lane | What would close it |
| --- | --- | --- | --- |
| Obligation-instance identity and OM-01 executability | engineering plus architect identity decision | GY-N9 / runtime-quality + PDC waist | An individual obligation can be removed while class totality remains green and the authority result turns red (policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476). |
| Canonical family declaration, chronology verification, current-head aggregate projection, and public owner statement | engineering plus architect product decision | confidence ledger / GY-N11 | Live-source recomputation over exact members and current heads without weakening per-problem scopes (policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476). |
| Constructed independence for `bounded_complete` | additional research followed by engineering/institutional execution | no canonical producer yet; S0-GAP-02 is only a partial adjacent dependency | A competence- and common-mode-aware independence profile with falsifiers and admitted evidence. |
| Selection-valid local theorem for outcome-dependent repair | additional research | confidence-ledger/N11 theorem lane | A useful theorem and verifier valid for the actually history-selected procedure. |
| Fresh decisive/adjacent cases, named humans, materiality owner evidence, and sealed custody | institutional/engineering execution | INT-R9 consumers plus S0-GAP-02 and existing owners | Real owner evidence and pre-result custody; no research artifact can self-supply it. |
| Independent benchmark oracle/evaluator custody | existing commissioned research | S0-GAP-02 | Delivery and independent acceptance of the commissioned benchmark architecture (policy-engine/docs/research/policy-operations/consolidation/stage0/stage0-additional-research-register.md:75-210). |

## 7. Method evidence from the correction chain

This wave is itself evidence for the project's method. A blocking multiplicity path was first found
in INT-R9. The first explanation then propagated a root-budget shortcut into the GY gap register,
the original INT-R10 research, its fixture, and the INT-R9 amendment's sibling summary. The INT-R10
audit enumerated the whole live schedule/registry, refuted the shortcut, and forced a revision; the
revision verification independently reproduced the corrected envelope. The chain reached four
substantive documents before correction.

The lesson is not that audit is unreliable. It is that an audit conclusion can itself become an
unaudited premise downstream. Set-level and arithmetic claims must be reproduced from the pinned
owner, and a correction must follow every dependent binding rather than only the originating file.
This lesson is routed separately to the failure-pattern register and a short always-on executor rule.

## 8. Consolidated standing

- **Ratifiable now:** the authority-band constraints in `int-wave-ratification-candidates.md`.
- **Retain as research:** the exact fixed-family theorem, source-specific envelope, protocol designs,
  transfer ledgers, and fixtures under their qualifications.
- **Repository fixes:** GY-GAP1, GY-GAP2, GY-DEF5, and the stale INT-R9 YAML binding.
- **Additional research:** constructed independence for obligation coverage and selection-valid
  composition for outcome-dependent repair.
- **Verified-pending:** INT-R9 amendment conformance at this pin.
- **Not authorized:** implementation, owner appointment, benchmark passage, promotion, or amendment
  of any plan or decision.
