---
title: "INT-R1 — Amendment Verification"
status: delivered
kind: amendment-verification
research_task: INT-R1
verification_verdict: CONFORMS_WITH_GAPS
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r1-amendment-verification
verified_branch: research/int-r1-amendment
verified_commit: 66baff37c7f566fc770377ba6c66a8dc7b517ce0
current_repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
authoritative_for:
  - bounded verification that the INT-R1 amendment executed the independent audit revision list
  - disposition of R1-R11, the audit consolidation conditions, and the preserved commendations
  - identification of amendment provenance and anchor-quality gaps before consolidation
may_not_use_for:
  - a new audit of the original INT-R1 research
  - re-litigation of formal conclusions settled by the independent audit
  - production implementation authorization
  - final code, wire, schema, package, or database contract
  - canonical owner appointment
  - authority grant or capability claim
  - current issuance of bounded_complete
  - legal compliance conclusion
  - benchmark passage
  - merger, release, or production approval
research_only: true
---

# INT-R1 — Amendment Verification

## 1. Executive verdict

**Verdict: `CONFORMS_WITH_GAPS`.**

The amendment **did execute the substantive audit corrections**. All R1-R11 revisions are present
in the amended research files; none was silently omitted or declined. The ten consolidation
conditions in the independent audit and the eleven-item acceptance checklist in the recommended
revision are satisfied in substance. The reduction of the primary deliverable from 1,629 to 833
lines did not delete the load-bearing qualifications. The amendment moved the most important
qualifications into the Executive Finding and the formal result itself:

- the impossibility result is premise-relative and requires a per-scope closure disposition;
- the positive result is a **Conditional Relative-Inclusion Theorem**;
- compiler semantic completeness and validator soundness remain assumptions that INT-R1 does not
  prove;
- independent review, mutation, governance, no-known-defeater review, and currentness are a
  separate governed admissibility protocol rather than logical truth-generators;
- current PolicyOS cannot issue `bounded_complete`;
- `OM-01` is explicitly blocked on `GY-GAP1`;
- the live obligation enum is preserved as a legitimate governed denominator, while only its
  universal-world interpretation is rejected;
- self-oracles and self-attested independence remain prohibited;
- the two red authority booleans remain false under a decisive omission or validator fault; and
- correction, reissue, and replay remain append-only.

No blocking or material conformance defect was found. Two minor gaps remain:

1. **Audit-head provenance is stale.** Every amended research file and the amendment ledger records
   `amended_after_audit: research/int-r1-independent-audit@0893a739...`. Direct comparison shows
   that the audit branch HEAD is
   `887bce985e6797c1a94dba24f33c6424ab09c0a5`, not `0893a739...`. Commit `887bce98...`
   corrected the final claim-evidence summary after `0893a739...`. This does not change the audit
   verdict or the amendment's substantive correctness, but the frontmatter does not satisfy the
   original requirement to pin the audit **HEAD**.
2. **Two plan citations are substantively correct but navigationally weak.** The amended files
   repeatedly cite the oversized `revised:` metadata line at line 7 of the Atlas and GY plans for
   DS17, `GY-DEF5`, and `GY-GAP1`, instead of citing the substantive task/gap blocks farther down
   those plans. Both line-7 statements support the attributed facts; neither is a false anchor.

The first gap should be corrected before consolidation records the amendment as fully conformant.
The second may be repaired during the same mechanical pass or carried as an explicit minor anchor
quality limitation. No re-research or second audit is required.

## 2. Verification basis and method

### 2.1 Pinned objects

| Object | Ref |
| --- | --- |
| Main baseline | `978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d` |
| Amendment branch | `research/int-r1-amendment` |
| Amendment HEAD | `66baff37c7f566fc770377ba6c66a8dc7b517ce0` |
| Audit branch | `research/int-r1-independent-audit` |
| Actual audit HEAD | `887bce985e6797c1a94dba24f33c6424ab09c0a5` |
| Audit commit currently named in amendment frontmatter | `0893a739e4739a6cd31dd95bc0b88526e1ff29ae` |

The amendment diff is eight commits and seven files: six amended INT-R1 research artifacts plus
one new amendment ledger, with `+2,384 / -2,925`. No audit file, source file, test, plan, or other
pre-existing document is in that diff.

### 2.2 Scope discipline

This pass used the independent audit as the settled baseline. It did not re-prove either theorem,
reassess external literatures, or search for new research questions. The checks were:

1. compare each R1-R11 requirement with the amended text;
2. compare each audit consolidation condition and acceptance gate with the amended text;
3. locate each of the thirteen audit commendations in the amended files, independently of the
   amendment ledger;
4. classify substantive additions in the amendment diff;
5. verify changed/new repository cross-references at the pinned baseline;
6. inspect the exact diff boundary; and
7. read `int-r1/amendment-ledger.md` only after the independent view was formed.

### 2.3 Anchor inheritance rule

The original audit exhaustively verified 31 unique census-anchor groups at
`d152565dcc11cea457dacd61fadc6e15dc3ecc86`. A comparison from that audit baseline to
`978e6b958...` shows that no anchored core source file changed. The only modified pre-existing
files relevant to the amendment were:

- `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md`; and
- `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md`.

All other changes in that interval are the delivered INT-R1/INT-R9 research and audit files. The
verification therefore reused the audit's settled result for unchanged core anchors and directly
rechecked the new GY/Atlas plan claims at `978e6b958...`. This is the bounded verification rule,
not a second anchor audit.

## 3. Finding register

| Finding | Severity | Disposition | Result |
| --- | --- | --- | --- |
| `INT-R1-V-001` | commendation | verified | R1-R11 are all executed; no revision was silently omitted or declined. |
| `INT-R1-V-002` | commendation | verified | The ten audit §15 consolidation conditions and eleven recommended-revision acceptance gates are satisfied in the amended text. |
| `INT-R1-V-003` | commendation | verified | All thirteen audit commendations survive in substance despite the primary document shrinking by roughly half. |
| `INT-R1-V-004` | minor | correct before full conformance | `amended_after_audit` pins `0893a739...`, but the actual audit branch HEAD is `887bce98...`. The stale ref appears in all six amended research artifacts and the amendment ledger. |
| `INT-R1-V-005` | minor | re-anchor or carry explicitly | Atlas and GY plan claims are repeatedly cited to line 7 revision metadata rather than substantive blocks. The claims are supported, but navigation is weak. |
| `INT-R1-V-006` | commendation | verified | No unmarked new load-bearing claim was introduced; additions are audit-mandated narrowings, verified downstream registrations, or explicitly noncanonical/open implementation sketches. |
| `INT-R1-V-007` | commendation | verified | Audit bundle, source, tests, plans, other documents, owner boundaries, one-lattice rule, INT-R9 ownership, and Stage-0 kernel constraints remain intact. |
| `INT-R1-V-008` | commendation | verified | The halving removed repetition and overclaim rather than the qualifications; the strongest qualifications now appear in the Executive Finding and theorem statements. |

**Counts:** blocking `0`; material `0`; minor `2`; commendation `6`.

## 4. Check 1 — revisions and consolidation conditions

### 4.1 R1 — conditional inclusion, not assumption discharge

**Executed.** The Executive Finding says:

> “Compiler semantic completeness and validator soundness are assumptions in that theorem. INT-R1
> does not prove them.”

It then separates independent reperformance, mutation, governance, no-known-defeater review, and
currentness into “a separate governed admissibility protocol” that “do[es] not create semantic
truth by themselves”
(`policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:35-76`).

The body repeats the distinction in two separate subsections:

- §4.2, **Conditional Relative-Inclusion Theorem**, contains D1-D6 and explicitly says D4 and D6
  are assumptions that INT-R1 does not prove; and
- §4.3, **Governed admissibility protocol**, classifies independence, reperformance, mutation,
  no-known-defeater review, currentness, and projection integrity as evidence/admission criteria,
  not logical truth-generators
  (`...int-r1-obligation-coverage-and-open-world-completeness.md:330-432`).

The formal supporting note gives the same split in §§8-9 and states that D4 “assumes
completeness” and D6 “supplies correctness”
(`policy-engine/docs/research/policy-operations/int-r1/open-world-impossibility-and-relative-coverage.md:285-405`).

### 4.2 R2 — per-scope closure-premise disposition

**Executed and applied.** The three values appear in the Executive Finding, the formal result, the
typed artifact, and benchmark faults:

- `closed_by_competent_basis`;
- `open_under_unseen_extension`; and
- `closure_not_established`.

The main result states that only the first may rule out the unseen-extension premise and only for
its exact owner, mandate, scope, purpose, interval, and challenge route. The other two retain the
unknown remainder and block the affected protected action
(`...int-r1-obligation-coverage-and-open-world-completeness.md:39-55`, `:300-357`).

The formal note devotes §4 to the meaning, evidence, effect, and non-transfer rules for each value
and expressly says closure for one jurisdiction, owner, purpose, or interval does not close another
(`...open-world-impossibility-and-relative-coverage.md:145-235`). The artifact sketch binds the
value to `ClosurePremiseEvidence`, and the benchmark includes unsupported-closure and scope-
transfer mutants. The vocabulary is therefore operationally applied as a research rule, not only
declared.

### 4.3 R3 — no current `bounded_complete`

**Executed in every required location.** The current refusal appears:

- in the Executive Finding: “PolicyOS cannot issue `bounded_complete`”;
- in the capability table and §4.4 of the primary deliverable;
- wherever the three assessments are introduced, where `bounded_complete` is a “future governed
  assessment only”;
- at the top of the artifact sketch, where the positive branch is explicitly unreachable in the
  current repository;
- in the formal note's current-capability and assessment sections; and
- throughout the benchmark, including the future-positive fixture caveat.

The artifact sketch states:

> “A producer-populated field that says ‘independent’ is not evidence of independence.”

and maps a current attempted protected use to `open_world_unresolved`
(`policy-engine/docs/research/policy-operations/int-r1/artifact-and-state-machine-sketch.md:31-75`,
`:285-335`, `:660-735`). S0-GAP-02 remains a dependency rather than a self-populated field.

### 4.4 R4 — OM-01 standing

**Executed by selecting the blocked option.** The primary report states:

```text
OM-01 standing = prototype_blocked_on_instance_model
blocking dependency = GY-GAP1
```

and forbids any claim that OM-01 is runnable or passed until the gap closes
(`...int-r1-obligation-coverage-and-open-world-completeness.md:515-555`).

The benchmark repeats:

> “OM-01 = conceptually required, currently blocked”

and specifies the missing pre-aggregation collection, semantic instance identity,
instance-to-class aggregation, injection point, independent comparison point, and propagation
chain without freezing a wire form
(`policy-engine/docs/research/policy-operations/int-r1/benchmark-and-edge-case-fixtures.md:115-220`).
Every later OM-01 execution statement is future-conditional or explicitly marked blocked.

### 4.5 R5 — narrowed Rule-12 disposition

**Executed.** The amendment now says:

> “Versioned coarse class vocabulary, routing key, budget stratum, or declared receipt denominator
> — Legitimate governed vocabulary. Gate participation does not remove Rule 12's exemption.”

It separately characterizes only the use of that enum as evidence of all world obligations as
unsupported/defective. It says no actual unrepresentable obligation was established and that the
choice among adding a class, extension family, instance layer, or another representation is not
decided by INT-R1
(`...int-r1-obligation-coverage-and-open-world-completeness.md:205-238`).

The text expressly says it neither orders nor licenses an enum change and that the enum “must not
be opened or dissolved.” This matches GY-DEF5 at the pinned GY plan. No sentence licenses opening,
dissolving, or making the live waist discoverable.

### 4.6 R6-R11 — accuracy repairs

All six are executed:

- **R6:** *Normative Systems* is now bibliographic orientation only; the catalog is expressly
  denied as support for detailed doctrine, and the theorem stands on its own definitions
  (`...int-r1-obligation-coverage-and-open-world-completeness.md:265-285`;
  `policy-engine/docs/research/policy-operations/int-r1/external-primary-source-ledger.md:30-82`).
- **R7:** the contributor anchor now supports only architecture, quality, testing, and
  documentation governance and explicitly does not locate every canonical authority owner
  (`...int-r1-obligation-coverage-and-open-world-completeness.md:150-165`;
  `...int-r1/repository-census-and-anchor-ledger.md:45-75`).
- **R8:** `NO_COVERAGE_BLOCKER` is noncanonical prose shorthand and may not be persisted, exported,
  ordered, rendered, counted as satisfaction, or consumed as promotion
  (`...int-r1-obligation-coverage-and-open-world-completeness.md:675-715`;
  `...int-r1/artifact-and-state-machine-sketch.md:575-635`).
- **R9:** the fixture claim is narrowed to class-counting, marker-presence, normative-row, and
  generic accessibility-token checks that do not bind district semantics; it disclaims an
  undefined semantic keyword oracle
  (`...int-r1-obligation-coverage-and-open-world-completeness.md:535-555`;
  `...int-r1/benchmark-and-edge-case-fixtures.md:245-280`).
- **R10:** the empirical claim is scoped to the pinned W12.D/G5 snapshot and expressly denied as
  an exhaustive history claim
  (`...int-r1-obligation-coverage-and-open-world-completeness.md:240-263`;
  `...int-r1/repository-census-and-anchor-ledger.md:300-330`).
- **R11:** stable identifiers are used for Cook and the corrigendum, DeMillo et al., NASA MC/DC,
  and Ramdas et al.; page details are not used as unsupported substantive proof
  (`...int-r1/external-primary-source-ledger.md:83-125`, `:300-390`).

### 4.7 Audit §15 conditions and recommended-revision checklist

All ten §15 conditions and all eleven checklist gates are satisfied in the amended text. The
claim-by-claim disposition and quoted fragments are in
[int-r1-amendment-conformance-ledger.md](int-r1-amendment-conformance-ledger.md). None was
explicitly declined.

The stale `amended_after_audit` SHA is a separate frontmatter-provenance gap; it does not negate
execution of R1-R11 or the substantive consolidation conditions.

## 5. Check 2 — preservation of the thirteen commendations

The independent view was formed before reading the amendment ledger. All thirteen audit
commendations survive in the amended artifacts. The full mapping by finding ID, location, and
quoted fragment is in the conformance ledger. The principal preservation results are:

1. the repository evidence base remains intact; core anchored sources did not change between the
   audit baseline and amendment baseline;
2. external transfers retain explicit non-transfer limits;
3. the five non-closure mechanisms remain expressly denied as closure proofs;
4. the five-row P29 stopping taxonomy remains intact;
5. self-oracles remain invalid and S0-GAP-02 remains unresolved;
6. no benchmark passage is claimed and `semantic_test_missing` remains current;
7. producer self-attestation cannot establish independence or bounded coverage;
8. coverage assessments remain inputs to one existing lattice and never auto-promote;
9. typed artifacts, state machine, challenger, reissue, and all required edge cases remain;
10. the red chain still sets both protected action and current public claim to false;
11. the diff remains research-only; and
12. the corrected orientation facts, including the true 15-member denominator, remain explicit.

The halving did not move qualifications into a footnote. The Executive Finding now contains the
premise-relative theorem, assumption status, current capability refusal, one-lattice effect,
relative public rider, append-only correction, enum protection, and OM-01 block before the reader
reaches §1.

## 6. Check 3 — added substantive claims

The amendment necessarily adds new wording because the audit required new dispositions. Added
substantive claims were classified as follows:

| Added claim family | Classification | Verification |
| --- | --- | --- |
| Three per-scope closure dispositions and only-first-defeats rule | audit-mandated narrowing | Required by R2; applied in main, formal note, artifact, and benchmark. |
| Current `open_world_unresolved` steady state and DS17 interpretation | audit-mandated current-capability consequence | Required by R3; Atlas Rev 3.10 at the pinned plan states the same consequence. |
| `GY-DEF5` as a claim/docstring defect, not enum defect | audit-mandated narrowing plus verified downstream registration | Required by R5; pinned GY plan says the enum must not be opened or dissolved. |
| `GY-GAP1` and OM-01 block | audit-mandated benchmark disposition plus verified downstream registration | Required by R4; pinned GY plan states current instance omission is unrepresentable. |
| Pre-aggregation instance fields and `bounded_current_future` | explicitly noncanonical research sketch | Marked as future, local, unfrozen, and unreachable at the pinned repository. |
| Expanded closure, independence, projection, and prerequisite mutants/fixtures | design consequences of R2-R4/R8-R9 | Explicitly research-only; no execution or passage claim. |
| Stable DOI/report identifiers | bibliographic normalization | Required by R11. |
| `amended_after_audit@0893a739...` as audit HEAD | **incorrect provenance claim** | Actual audit branch HEAD is `887bce98...`; finding V-004. |

No other added load-bearing factual claim was found that lacked either audit authorization,
direct repository support, or explicit open-question/design-only classification.

### 6.1 Downstream cross-reference verification

At `978e6b958...`:

- Atlas Revision 3.10 states that independence is not constructed, the repository cannot issue
  `bounded_complete`, and DS17 must render `open_world_unresolved` as a steady state rather than a
  loading placeholder.
- GY Revision 23 registers `GY-DEF5` as a claim defect in “Universal,” says the enum must not be
  opened/dissolved, and registers `GY-GAP1` as the absence of obligation-instance identity that
  prevents OM-01 execution.

The amendment represents both accurately. It does not import GY-GAP2 or resolve INT-R9's
sequence-level multiplicity.

## 7. Check 4 — anchor verification and frontmatter-anchor set

### 7.1 Result

No broken path, nonexistent range, or substantively contrary anchor was found in the amendment.
The unchanged core anchor base retains the original audit's verified standing because no anchored
core file changed from `d152565d` to `978e6b958`.

The only changed pre-existing anchor sources were the Atlas and GY plans, and their new claims were
checked directly. Both support the amendment's attribution.

### 7.2 Weak frontmatter/revision-line anchors

The complete unique set is:

| Anchor | Amended claims supported | Verification | Disposition |
| --- | --- | --- | --- |
| `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:7` | DS17 treats `open_world_unresolved` as current steady state; future positive value must render with basis | line 7 says exactly this in Revision 3.10, but it is oversized revision metadata rather than the substantive DS17 task block | minor; re-anchor for navigation |
| `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:7` | `GY-DEF5` targets “Universal,” enum must not be opened/dissolved; `GY-GAP1` blocks OM-01 | line 7 says exactly this in Revision 23, but it is oversized revision metadata rather than the Registered gaps/defect blocks | minor; re-anchor for navigation |

These two anchors recur across the main report and supporting artifacts. Repetition does not make
them false, and only two unique metadata lines carry the weakness. The pattern is therefore minor,
not material. Consolidation should prefer substantive block anchors when available.

## 8. Check 5 — boundaries and frontmatter

### 8.1 Diff boundary

Direct comparison of `978e6b958...66baff37...` shows exactly seven changed paths:

- the six INT-R1 research artifacts; and
- `int-r1/amendment-ledger.md`.

Consequently:

- the audit bundle was not edited;
- no file under `policy-engine/src/` changed;
- no test changed or was added;
- no plan or other pre-existing document changed; and
- the amendment did not edit the branch it was meant to verify.

### 8.2 Authority and architecture boundaries

The artifacts remain sketches. They repeatedly state that no canonical owner, package, API,
persistence format, generated client, wire shape, or authority grant is established. The
pre-aggregation fields are explicitly a research requirement rather than a frozen schema.

No parallel status lattice is created. `NO_COVERAGE_BLOCKER` is expressly noncanonical and the
current/future coverage assessments feed only existing `failed`, `unknown`, or
`scope_insufficient` effects. A future positive branch removes only an additional refusal and
never sets `satisfied` or promotion.

INT-R9's multiplicity question is explicitly deferred in the primary report's §10. The amendment
does not compose multiple risk scopes, change δ, or claim to resolve INT-R9/INT-R10.

No Stage-0 kernel statement is weakened. The amendment preserves no-authority-by-observation/
transport/projection/passage, band-sensitive fail-closed behavior, evidence currentness, canonical
owner reaction, and append-only custody.

### 8.3 Frontmatter result

The following fields are honest across the six amended research files:

- `result_type: accepted_narrow_scope` for the research result and `confirmed` only for the
  factual repository census;
- `repository_branch: research/int-r1-amendment`;
- `current_repository_commit: 978e6b958...`;
- `research_only: true`;
- `may_not_use_for` exclusions covering implementation, final contract, owner appointment,
  authority, compliance, benchmark passage, and current `bounded_complete` issuance.

The exception is `amended_after_audit`. The audit branch currently resolves exactly to
`887bce985e6797c1a94dba24f33c6424ab09c0a5`; comparing that commit to the branch is
`identical`. Commit `0893a739...` is an earlier valid audit commit, followed by the
`887bce98...` correction to the claim-evidence summary. Therefore every amended frontmatter and
the amendment ledger should replace:

```yaml
amended_after_audit: research/int-r1-independent-audit@0893a739e4739a6cd31dd95bc0b88526e1ff29ae
```

with:

```yaml
amended_after_audit: research/int-r1-independent-audit@887bce985e6797c1a94dba24f33c6424ab09c0a5
```

## 9. Final disposition

The amendment is substantively ready for consolidation. It did not lose the audit's load-bearing
qualifications, did not turn assumptions into proved facts, did not self-score, did not create a
parallel lattice, did not license an enum redesign, and did not claim current capability.

Full `CONFORMS` standing requires one mechanical provenance repair: pin the actual final audit HEAD
in the six amended research files and the amendment ledger. Re-anchoring the two plan metadata
citations is recommended but not a substantive precondition. After the provenance correction,
no item from R1-R11 or the audit consolidation conditions remains open.
