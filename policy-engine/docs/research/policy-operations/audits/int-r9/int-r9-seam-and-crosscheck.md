---
title: INT-R9 — S0-GAP-02 Seam and INT-R1 Cross-Check
status: delivered
kind: independent-audit
research_task: INT-R9
audit_verdict: NO_GO
repository: https://github.com/DenisKopylov/polisyos
audited_branch: research/int-r9-first-promotion-protocol
audited_commit: f5ad922377e38ee3ddbecb33293300bca25a9ad7
current_repository_commit: d152565dcc11cea457dacd61fadc6e15dc3ecc86
int_r1_branch: research/int-r1-obligation-coverage
int_r1_commit: 82e136a8d528cb24e661973ac1a8ea4fb6f1c80f
inspection_date: 2026-08-03
authoritative_for:
  - independent determination of whether INT-R9 duplicates S0-GAP-02 ownership
  - independent compatibility determination between delivered INT-R9 and delivered INT-R1 research results
  - consolidation constraints for the two seams at the pinned commits
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, package, or database contract
  - canonical owner appointment
  - authority grant or capability claim
  - benchmark passage
  - creation of a replacement oracle framework
  - reinterpretation of INT-R1 as unconditional open-world completeness
research_only: true
---

# INT-R9 — Seam and Cross-Check

## 1. Bottom-line determinations

### S0-GAP-02

**Verdict: compatible with minor-to-material wording repair; no substantive second owner was
created.**

INT-R9 mostly does what the task required: it states first-event-specific properties and defers
generic oracle/evaluator machinery to S0-GAP-02. The 852-line YAML repeats many required
properties at high resolution, but it does not select cryptographic primitives, key storage,
access-control implementation, evaluator code, rotation service, or challenge platform. The
remaining risk is the phrase “S0-GAP-02 or a consolidation-approved equivalent,” which could be
read as permission to create a sibling framework rather than to adopt or formally supersede the
canonical owner.

### INT-R1

**Verdict: semantically compatible only after material interface correction.**

INT-R1's actual result satisfies the conceptual need for a versioned, scoped obligation-coverage
input, but not the literal INT-R9 interface as written. INT-R1 delivers a research shape named
`ObligationCoverageEnvelope`, not `ObligationSetDeclaration`. More importantly, its assessment
lattice does not permit a generic “narrow the criteria and public claim” response after weakness is
found. For the affected protected action:

- `bounded_complete` may support continued evaluation only relative to the exact declared closure
  basis, obligation language/compiler version, cutoff, assumptions, and current independent
  review, with the unknown-world rider visible;
- `known_incomplete` is NO-GO;
- `open_world_unresolved` is NO-GO whenever the unresolved remainder may be material; and
- candidate-band work may continue only with the ratified carried limitation.

A different, narrower protected action can be registered prospectively as a new exact scope. The
same scored claim cannot be silently narrowed after inspection.

## 2. S0-GAP-02 source of truth

The commissioned S0-GAP-02 record at
`docs/research/policy-operations/consolidation/stage0/stage0-additional-research-register.md:113-190`
asks how an implementation-independent, machine-readable, challengeable oracle can:

- keep expected results sealed;
- preserve ambiguity and dissent;
- prevent shared-code circularity;
- resist memorization;
- supply an independent evaluator interface and code-independence rules;
- supply a sealed expectation format with alternatives;
- govern commitment, custody, access logs, rotation, challenge, and supersession;
- generate adjacent and metamorphic mutations; and
- issue a reproducibility receipt and bounded-claim template.

Its falsifiers include evaluator imports from implementation owners, visible expected labels,
semantic instability under ID renaming or adjacent cases, shared reducer faults, silent oracle
correction, and discarded reviewer conflict or dissent.

This is an explicit generic owner commission. INT-R9 cannot duplicate it merely because first
promotion also needs sealed answers.

## 3. Ownership comparison

| Mechanism | S0-GAP-02 standing | INT-R9 standing at audited commit | Audit disposition |
| --- | --- | --- | --- |
| canonical package serialization | explicit S0-GAP-02 deliverable | named as required property and deferred | reuse; no duplicate owner found |
| hiding/binding commitment | explicit S0-GAP-02 deliverable | requires both properties, declines primitive choice | reuse |
| key/secret management | implied by custody/access design | expressly deferred | reuse |
| independent timestamp/transaction proof | commitment/custody responsibility | required property, mechanism deferred | reuse |
| least-privilege access and logs | explicit deliverable | required property, implementation deferred | reuse |
| dual-control reveal | within custody/access protocol | required property, implementation deferred | reuse |
| evaluator interface/code independence | explicit deliverable and falsifier | consumes evaluator version/package; does not design evaluator code | reuse |
| clean rebuild/reference semantics | explicit deliverable | not re-owned | reuse |
| reviewer rotation/succession | explicit deliverable | requests named alternates and defers generic policy | reuse plus first-event panel instance |
| challenge and inter-reviewer adjudication | explicit deliverable | state machine points to S0-GAP-02 path | reuse |
| oracle correction/supersession | explicit falsifier/deliverable | requires append-only first-claim correction | shared machinery, distinct first-claim consequence |
| adjacent/metamorphic generator | explicit S0-GAP-02 deliverable | states first-promotion adjacency property and case-pair rule | potential boundary contact; generator remains S0-GAP-02 |
| finite first-event queue | not S0-GAP-02's long-cycle focus | exact INT-R9 delta | distinct |
| committed random selection and order | not named by S0-GAP-02 | exact INT-R9 delta | distinct |
| no slot substitution | not generic oracle ownership | exact INT-R9 delta | distinct |
| firstness definition | not S0-GAP-02 | exact INT-R9 delta | distinct |
| result-independent refusal/exhaustion publication | generic retention overlaps, first-event consequence distinct | exact INT-R9 delta | distinct with shared retention machinery |
| no-case-specific-code historical provenance review | S0-GAP-02 resists memorization but does not define first-event implementation-history disposition | exact INT-R9 delta | distinct |
| useful-design-rate enforcement surface | outside S0-GAP-02 | exact INT-R9 delta | distinct |
| correction of historically first public claim | S0-GAP-02 corrects oracle; INT-R9 corrects PolicyOS's first-promotion claim | exact INT-R9 delta | distinct canonical consumer reaction required |
| sequence-level risk family | not an S0-GAP-02 oracle function | asserted by INT-R9 but unresolved against N9 scopes | separate blocking INT-R9 research gap, not a reason to expand S0-GAP-02 |

## 4. Does the YAML duplicate S0-GAP-02?

The YAML contains detailed sections for:

- required package contents;
- commitment properties;
- independent custodian signature;
- access principals and immutable logs;
- dual control;
- leak handling;
- panel calibration; and
- dispute escalation.

That density creates contract risk, but ownership is still described as `reuse_S0-GAP-02`. The
file does not choose an algorithm, key store, service, package, schema owner, or evaluator
implementation. It is therefore not yet a second framework in substance.

The wording must nevertheless be tightened in consolidation. “A consolidation-approved
equivalent” is safe only if it refers to an explicit decision that supersedes S0-GAP-02 as the
single canonical architecture. It is unsafe if it permits an INT-R9-local service that merely
claims equivalent properties.

### Finding `INT-R9-H-001` — commendation

Preserve the explicit reuse/defer table and the prohibition on a second framework.

### Finding `INT-R9-H-003` — minor

Remove or constrain the “equivalent” escape hatch so P27/P28 cannot be satisfied by declaration.

## 5. INT-R1 actual result

The delivered INT-R1 report at commit `82e136a8...` establishes two results.

### 5.1 Impossibility result

No finite PolicyOS inspection can prove unconditional open-world obligation completeness. Two
worlds can be identical on every observed source, query, receipt, and validator while one contains
an additional unseen decisive obligation. A closure premise must come from a competent exhaustive
register, deliberately closed domain, valid closure rule, or exact-scope oracle assumed complete.
PolicyOS can verify and admit that premise; it cannot generally manufacture it from search.

### 5.2 Relative-coverage theorem

For a declared protected action, scope, cutoff, immutable closure basis, obligation language and
compiler version, and validator-governance configuration, PolicyOS can establish that every
obligation derivable from that basis and language was included and checked, subject to generic
traversal, relative compiler/validator soundness, independent reperformance, no known material
internal defeater, and currentness.

The public probability statement remains explicitly relative:

```text
P(false promotion with respect to the declared obligation set
  | maintained assumptions) <= delta
```

It may not become “all applicable obligations are complete” or a bound on the existence of an
unknown obligation.

### 5.3 Delivered research shape

The support artifact names an `ObligationCoverageEnvelope`. Its assessment postures are:

- `bounded_complete`;
- `known_incomplete`; and
- `open_world_unresolved`.

Those postures map consequence-sensitively into existing N9 outcomes such as failed, unknown, or
scope-insufficient. They are not a parallel authority lattice and do not mint promotion.

No canonical artifact named `ObligationSetDeclaration` was found in the delivered INT-R1 files.

## 6. INT-R9 declared interface

INT-R9 says it consumes a versioned `ObligationSetDeclaration` with:

- purpose and scope;
- obligations/classes;
- bounded-completeness posture;
- maintained assumptions;
- known unknowns;
- criticality and owner refs; and
- `may_not_use_for`.

It says a weaker result may “narrow the criteria and public claim” or create NO-GO. Its open
questions ask which weakness blocks and how a later obligation enters after sealing.

The semantic fields are close to INT-R1, but the artifact name and degradation rule are not.

## 7. Compatibility matrix

| INT-R1 result/input | Can INT-R9 anti-selection procedure continue? | Can the affected authority-band promotion be positive? | Required public meaning |
| --- | --- | --- | --- |
| `bounded_complete` relative to exact basis/language/cutoff, current and independently checked | yes | potentially, subject to every other owner/protocol gate and sequence-risk resolution | complete only within named basis/language; unknown world remainder visible |
| `bounded_complete` but stale, superseded, or challenged by a material new obligation | chronology remains valid; substantive evaluation pauses | no current positive | historical relative result retained; current use suspended/withdrawn pending new epoch |
| `known_incomplete` | yes as a published failed attempt | no | concrete omitted obligation or validator fault; affected action fails |
| `open_world_unresolved` with possible material remainder | yes as a published blocked attempt | no | closure basis/owner/source/scope/independent check unresolved |
| `open_world_unresolved` proven immaterial to a separately declared protected action | only under a prospectively registered exact scope and owner-backed materiality result | possibly for that distinct action, not by editing the old scored claim | narrow action and residual uncertainty explicitly identified |
| no INT-R1 envelope | preregistration may remain draft; sealing/evaluation not admissible | no | missing obligation-coverage input |
| later discovered material obligation after sealing | old custody chronology remains; append challenge and perturbation | current positive suspended/withdrawn until reissue | no silent edit; new basis, epoch, checks, and decision |

## 8. The correct degradation rung

INT-R9's phrase “narrow the criteria and public claim” is safe only prospectively. It must not mean:

1. inspect a case;
2. discover that obligation coverage is weak;
3. remove or reclassify the troublesome obligation or scope; and
4. keep the same scored attempt under narrower wording.

That would be post-result criterion/scope selection, exactly what INT-R9 forbids elsewhere.

The compatible interpretation is:

- the old attempt remains refused, disputed, or blocked under its sealed scope;
- a genuinely different protected action requires a new exact scope identity, closure basis,
  envelope, preregistration, and chronological record before result-bearing access; and
- the old result stays visible.

This interpretation is not a new protocol design; it is the minimum consistency condition between
the two delivered research results.

## 9. Does a weaker INT-R1 result invalidate INT-R9 entirely?

No. INT-R9 contains two separable layers:

1. **custody/anti-selection layer** — proves what was committed, revealed, attempted, refused,
   disputed, and published; and
2. **substantive promotion admissibility** — depends on INT-R1 and every other canonical owner.

A `known_incomplete` or `open_world_unresolved` envelope can make the current slot an honest NO-GO
without invalidating the chronology or publication record. That graceful degradation is real and
should be preserved.

It does not cure the three-slot multiplicity defect. The anti-selection chronology can be valid
while the family-wise numeric claim remains invalid.

### Finding `INT-R9-H-002` — material consolidation blocker

Replace the nonexistent interface name, bind the exact INT-R1 posture semantics, and prevent
post-inspection scope narrowing.

## 10. Interactions with INT-R5 and INT-R8

The audited report correctly treats these as live dependencies rather than solving them:

- **INT-R5** may determine competent delegation, named-person eligibility, and institutional
  authority evidence for authors, custodians, or adjudicators. INT-R9 cannot self-certify those
  external facts.
- **INT-R8** may determine public projection, disclosure, compression, challenge, and currentness
  semantics for promoted/refused/void/disputed/corrected/withdrawn records. INT-R9 requires equal
  auditability but must not create a competing public-record model.

No current contradiction was established because those sibling results were not part of this
cross-check. Consolidation must preserve the deferral.

## 11. Seam verdict

| Seam | Verdict | Consolidation action |
| --- | --- | --- |
| S0-GAP-02 ownership | compatible | preserve reuse; constrain “equivalent” to explicit canonical supersession |
| S0-GAP-02 property overlap | acceptable | keep INT-R9 first-event properties; do not implement duplicate custody/evaluator machinery |
| INT-R1 artifact name | incompatible as written | consume delivered `ObligationCoverageEnvelope` or an explicitly consolidated successor |
| INT-R1 theorem semantics | compatible narrowly | preserve relative-to-basis/language/cutoff rider |
| INT-R1 degradation | too permissive | known/material unresolved => NO-GO for affected action; any narrower action is prospective and separately registered |
| anti-selection chronology under INT-R1 NO-GO | compatible | publish blocked/refused attempt without erasing chronology |
| numeric three-slot family | unresolved | re-research under INT-R9/N9 confidence ownership; do not assign to S0-GAP-02 |

## 12. Final cross-check conclusion

INT-R1 does not refute the idea of a prospectively governed first-promotion attempt. It makes the
substantive claim narrower and more conditional than INT-R9's placeholder interface expresses.
S0-GAP-02 does not make INT-R9 redundant; it supplies generic evaluator custody that INT-R9 should
reuse.

The two seams are therefore repairable. They do not change the overall `NO_GO`, which is driven by
the independent multiplicity failure in INT-R9's three-slot sequence.
