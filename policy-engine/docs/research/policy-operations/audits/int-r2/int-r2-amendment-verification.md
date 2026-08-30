---
title: INT-R2 — Amendment Verification
status: complete
research_task: INT-R2
stage: 4
research_head: 5e6a7063da770122155af6300647d0cd2e9c17ea
audit_head: dbdb1243a277f0864cae9af240ff1d13786d99df
amendment_head: 0afc3779e2894f2793cc40150d6923589bd36ee6
verification_branch: research/int-r2-amendment-verification
verdict: CONFORMS_WITH_GAPS
authoritative_for:
  - independent stage-4 verification of the INT-R2 amendment against the stage-2 audit
  - row-level disposition reconciliation
  - named amendment-verification gaps
may_not_use_for:
  - amendment of the package, audit or amendment ledger
  - ratification
  - capability claim
  - owner, producer, auditor, grantor or signer appointment
  - production admission
  - gate opening
---

# INT-R2 — Amendment Verification

## 1. Scope, Method, And Topology

This verification measures the amendment against the stage-2 audit artifacts and the pipeline at the
pinned history. It does not grade the amendment against its own hand-back or against the stage-4
commission's summary.

The controlling amendment vocabulary is in
`docs/reference/policy-operations-research-pipeline.md:92-102`:

```text
accepted | accepted_with_variation | declined_with_reason
```

The controlling stage-4 rules are at
`docs/reference/policy-operations-research-pipeline.md:104-118`: anti-ratchet, environmental-limit
separation, and a vector verdict.

The verification read the audit's main register, claim-evidence ledger, formal-argument audit,
anchor/citation verification, seam crosscheck, orientation-error ledger and recommended revision. It
then read the four amendment-delta files and the unchanged union/fixture artifacts required for
invariant checks.

### 1.1 Topology

The branch was created from exact amendment head
`0afc3779e2894f2793cc40150d6923589bd36ee6`.

Authenticated GitHub connector comparisons before the headings-only write established:

| Required ancestor | Compare result | Merge base | Contained? |
| --- | --- | --- | --- |
| amendment `0afc3779e...` | `identical` | exact amendment head | yes |
| audit `dbdb1243a...` | `ahead_by: 7`, `behind_by: 0` | exact audit head | yes |
| research `5e6a7063d...` | `ahead_by: 15`, `behind_by: 0` | exact research head | yes |

The headings-only verification commit is
`c482f581e5a2008ed0bae54c769513a52eb4f99b`. After that write the branch was one commit over the
amendment, with the verification artifact as the only delta.

Topology dimension: **conforms**.

## 2. Environmental Coverage

The terminal environment has no local Git checkout. The requested local-ref and merge-base commands
therefore did not produce containment exit code `0`; each local Git operation failed before it could
evaluate the predicate. The `origin` remote is also unavailable in that non-repository directory.
A direct HTTPS `ls-remote` additionally failed DNS resolution for `github.com`.

This is **an environmental limit in my verification, not a package defect**.

The limit affects the terminal-transcript/transport-receipt dimension. It does not reverse the
connector evidence: the authenticated connector read the remote branch, exact commits and merge bases.
Connector results are labelled as connector results and are not represented as shell output.

Environmental coverage dimension: **gap in verifier coverage; not a package defect**.

## 3. Ground-Truth Denominators

### 3.1 Audit finding denominator

The authoritative audit register is the 16 table rows at
`audits/int-r2/int-r2-independent-audit.md:78-93`:

```text
12 defect rows:       F001-F012
 4 commendation rows: C001-C004
--------------------------------
16 finding rows
```

Severity arithmetic is row-derived:

```text
0 blocking + 9 material + 3 minor + 4 commendation = 16
```

### 3.2 Orientation observations are not 19 findings

The orientation ledger has six descriptive O-rows, and its result identifies:

- three consequential orientation errors: owner appointment, capstones overcalled structural, and the
  supplied zero;
- one separately unresolved supplied object: the draft consumer row;
- two other bounded observations.

The three consequential errors are not three additional severity-bearing findings:

- supplied zero overlaps commendation `C002`;
- owner-appointment language and structural overclassification have no separate severity row because
  the package rejected both;
- consumer-row non-reconstructability is `F012`, but it corresponds to orientation row `O-04`, not to
  one of the three consequential errors.

Therefore the amendment's conclusion **16 findings, not 19** is correct. Its explanatory bullet that
places `F012` inside the discussion of the three accepted errors is imprecise: `F012` is the separate
unresolved consumer object. This does not change the denominator.

Denominator dimension: **conforms, with one non-count-changing rationale imprecision**.

### 3.3 Amendment disposition rows

The amendment table at `int-r2/amendment-ledger.md:299-314` has exactly 16 rows:

```text
11 accepted_corrected
 1 accepted_residual_registered
 4 preserved
------------------------------
16 rows
```

These are table-row counts, not grep occurrences.

### 3.4 Finding-register rows and transition arithmetic

The stage-1 register had 40 rows:

```text
23 exact confirmed
10 exact accepted_narrow_scope
 1 deferred_open_problem
 6 mixed cells
--------------------------
40 rows
```

The six mixed rows were five `confirmed + prose` cells (F13, F27, F29, F31, F39) and one
`accepted_narrow_scope + prose` cell (F34). Exact normalization therefore first yields:

```text
28 confirmed
11 accepted_narrow_scope
 1 deferred_open_problem
--------------------------
40 rows
```

F32 then moves from `confirmed` to `accepted_narrow_scope`, producing the amended row distribution:

```text
27 confirmed
12 accepted_narrow_scope
 1 deferred_open_problem
--------------------------
40 rows
```

The additional occurrence of `blocked` is outside the register: it appears in the kill-rule prose
("a `blocked` result for the affected implementation"). There is no `blocked` research-standing row.

Register arithmetic dimension: **conforms**.

### 3.5 External-source denominator

The source ledger remains 22 table rows, derived by section:

```text
S01-S04   4
S05-S11   7
S12-S17   6
S18-S22   5
-----------
total    22
```

The six-column structure remains source → class → retained proposition → explicit non-effect → holder
label, with ID as the row key.

## 4. Disposition Vocabulary Verification

### 4.1 Registered vocabulary

Pipeline §3.3 permits only:

```text
accepted
accepted_with_variation
declined_with_reason
```

The amendment instead places `accepted_corrected`, `accepted_residual_registered` and `preserved` in
the governed disposition column. All three are invalid instance tokens.

### 4.2 Token mapping

| Amendment token | Registered mapping | Ruling |
| --- | --- | --- |
| `accepted_corrected` | `accepted` only where the audit closure condition is actually met; otherwise `accepted_with_variation` | **Not a clean one-to-one mapping.** The token encodes that some text moved, not whether the audit condition closed. F006 and F007 demonstrate the ambiguity. |
| `accepted_residual_registered` | `accepted_with_variation` | Clean mapping. The author accepts F008, preserves its safety requirement and records the unperformed closure work. It is not a functional decline. |
| `preserved` on C001-C004 | `accepted` | Commendations are rows in the audit finding denominator, and the requested response is preservation. `preserved` describes the effect but is not a registered disposition. |

`accepted_residual_registered` is not `declined_with_reason`: it does not dispute F008 or reject its
closing principle. It explicitly retains `semantic_test_missing`, names the required manifest and
mutants, and refuses to fabricate a pass.

### 4.3 Registered-vocabulary arithmetic

A purely lexical intent mapping would be:

```text
accepted                 15  = 11 accepted_corrected + 4 preserved
accepted_with_variation   1  = 1 accepted_residual_registered
declined_with_reason      0
---------------------------
total                    16
```

That mapping is not the verified substantive result. Against the audit closing conditions:

- F006 is only partially repaired;
- F007 supplies relation semantics but omits the required field-level vocabulary owner;
- F008 is intentionally carried open.

The verified registered-vocabulary reconciliation is therefore:

```text
accepted                 13
accepted_with_variation   3  = F006 + F007 + F008
declined_with_reason      0
---------------------------
total                    16

13 + 3 + 0 = 16
```

Disposition-schema dimension: **does not conform as written**. This is not only a naming defect,
because `accepted_corrected` masks two rows whose audit closure tests are not fully met.

## 5. Finding-By-Finding Verification

The result labels in this section are verification descriptions, not amendment dispositions or new
standing vocabulary.

| Audit row | Audit defect / commendation coordinate | Amendment response coordinate | Verification result | Independent ruling |
| --- | --- | --- | --- | --- |
| `F001` | audit `:78` | amendment `:299`; amended register §4 | **satisfied** | The register now carries kind, exact standing, evidence, source/transfer class, holder, consequence and non-effect in each row. |
| `F002` | audit `:79` | amendment `:300`; amended register §4 | **satisfied** | F13/F27/F29/F31/F34/F39 use exact registered standing tokens; qualifiers survive in kind/scope/basis. |
| `F003` | audit `:80` | amendment `:301`; baseline §3 | **satisfied** | The false `gy_waist.py:218-255` coordinate is removed. `gy_waist.py:1318-1325` contains `PromotionFailClosedReason` and exactly the five claimed tokens. |
| `F004` | audit `:81` | amendment `:302`; baseline §3; register F05/F07/F11/F32 | **satisfied** | Local positives are retained; each unwalked repository-wide zero is separately `not_established`. F32 is `accepted_narrow_scope` with holder `not_established`. |
| `F005` | audit `:82` | amendment `:97-154` | **satisfied at research-contract level** | Eight branch predicates, sibling falsifiers, P37 eligibility, data-gap and split rules, capstone application and a 14-row missing-input template are present. The fourteen correctly remain unclassified. |
| `F006` | audit `:83`; recommended revision §4 | amendment `:304`; S04/S13/S14 | **partially satisfied** | The three weakest overview coordinates were repaired, and the 22-row transfer structure remains strong. The audit closure test, however, requires exact source state/passages for every S01-S22 row or an explicit replay-unavailable statement. Mutable or under-located rows such as S02, S06, S08-S10, S12, S15-S18 and S22 still lack the required edition/section/content identity. This must be `accepted_with_variation`, not unqualified corrected. |
| `F007` | audit `:84`; formal audit §5; recommended revision §6 | amendment `:155-179` | **partially satisfied** | All twelve dimensions now have a relation, unknown/conflict rule and current status; four are local exact/interval checks and eight are deferred/fail-closed. The audit also required a vocabulary owner for each field. The matrix has no owner column and does not explicitly record `absent/unallocated` per vocabulary. This must be `accepted_with_variation`. |
| `F008` | audit `:85`; recommended revision §6 | amendment `:180-214` | **correctly carried open** | No 63-case pass is fabricated. The record supplies the future manifest fields, independent-oracle rule, ordinary data positive control and seven named mutants including `remove_property_keep_markers`; capability remains `semantic_test_missing`. This is a genuine red-first registration, but the audit closure test remains open. Registered disposition: `accepted_with_variation`. |
| `F009` | audit `:86` | amendment `:215-246` | **satisfied** | Open-world terminals require a content-bound coverage envelope; otherwise the maximum result is route exhaustion at an epoch or provisional refusal. Formal scoped negatives remain separate. |
| `F010` | audit `:87` | amendment `:247-272`; handoff §§1-2 | **satisfied** | `owner_writability` remains one discriminator with separately stateful substantive-authority and technical-grant conjuncts; neither closes the other. |
| `F011` | audit `:88` | amendment `:247-272`; handoff kill rules | **satisfied** | External HD is not IA without assurance and independence; favourable IA is not the underlying decision. Dependency references remain possible. |
| `F012` | audit `:89` | amendment `:273-290`; handoff §§1,3 | **satisfied** | The consumer demand is explicitly `institutionally_supplied`, has no immutable reconstructable source, and cannot establish existence, merge, ownership, readiness or authority. |
| `C001` | audit `:90` | amendment `:311`; baseline §5 | **preserved as required** | Proposition, denominator, executing/supplying party, P37 label and consequence remain intact. |
| `C002` | audit `:91` | amendment `:312`; baseline §5 | **preserved as required** | The supplied zero remains unsettled; no `zero_structural` claim is minted. |
| `C003` | audit `:92` | amendment `:313`; amendment `:247-272` | **preserved as required** | Eight discriminators and all 28 pair distinctions remain. Only the two authorised refinements were added; no ninth type exists. |
| `C004` | audit `:93` | amendment `:314`; source ledger | **preserved as required** | The 22-row transfer/non-effect structure remains. F006's replay gap is independent of this commendation. |

Per-finding result:

```text
satisfied / preserved as required       13
partially satisfied                      2  (F006, F007)
correctly carried open as variation      1  (F008)
------------------------------------------
total                                   16
```

Every audit row has a verification result.

## 6. In-Place Versus Additive Correction

### 6.1 In-place corrections that were required and made

- F01's false coordinate is corrected in the baseline and amended register.
- F05/F07/F11/F32 no longer leave sampled local evidence attached to a repository-wide zero.
- All six mixed standing cells are corrected in the register, with qualifier information retained.
- The consumer-row claim is holder-labelled in the handoff and register.
- S04/S13/S14 are corrected in the source ledger rather than merely contradicted by an appendix.

### 6.2 Additive constructions that were appropriate

- F005 classifier predicates and sibling falsifiers add missing operational semantics to a still-valid
  pre-union design.
- F007's matrix correctly treats the original envelope as a target field family rather than current
  aggregate capability; the remaining problem is the omitted vocabulary-owner field, not the additive
  placement itself.
- F008's manifest/mutant requirements correctly amend a proposed protocol without pretending to have
  executed it; F34/F35 were also narrowed in place.
- F009's bounded coverage envelope is a valid condition on candidate open-world terminals.
- F010/F011 add contract invariants without restructuring the union cleared by the audit.

### 6.3 Inconsistency found

The amendment's criterion says under-identified source states are corrected in place, but it applies
that rule only to S04/S13/S14. The audit's complete 22-row closure test identifies additional mutable
or under-located rows. Those original rows remain under-identified and are not expressly marked
replay-unavailable. This is the same substantive F006 gap, not a second finding.

No other false factual anchor or overbroad repository zero found by the audit remains standing in an
authoritative package row.

Correction-mode dimension: **conforms except for the bounded F006 incompleteness**.

## 7. Invariant Verification

| Invariant | Result | Evidence-based ruling |
| --- | --- | --- |
| Audit verdict remains `GO_WITH_REVISIONS` | **conforms** | Amendment frontmatter records it and explicitly says stage 3 does not lift it. |
| `research_standing: accepted_narrow_scope` | **conforms** | Unchanged in amendment ledger and amended register. |
| `capability_standing: absent/unallocated` | **conforms** | Unchanged; exact benchmark/evaluator/producer capabilities remain absent. |
| `gate_standing: NO_GO` | **conforms** | Unchanged. |
| Eight union types, no ninth | **conforms** | Main union still enumerates exactly GR, EB, OW, LM, NA, IC, HD and IA; compound gaps use ordered cases. |
| No cross-substitution | **conforms** | Writability conjuncts, HD↛IA and IA↛underlying-decision rules are explicit. |
| Source ledger has 22 rows and same structure | **conforms** | Row derivation is 4 + 7 + 6 + 5 = 22; only three source coordinates were strengthened. |
| C001-C004 preserved, not spent as credit | **conforms** | Four separate rows remain in the 16-row arithmetic; amendment states preservation creates no credit. |
| No institutional holder appointed | **conforms** | Changed text uses candidate/likely/external/later-appointment language and keeps all institutional acts out of scope. |
| Fourteen residuals not invented/classified | **conforms** | Amendment supplies missing-input schema and retains `not_established`. |
| F008 capability label remains honest | **conforms** | `semantic_test_missing`; no `0/63` pass or oracle appointment claimed. |

Invariant dimension: **conforms**.

### 7.1 Zero declines

Zero `declined_with_reason` rows is not itself a defect. The audit had already refuted the package-level
T4 charge and the strongest T6 charge; those outcomes appear as commendations or narrowed findings,
not invalid audit rows. No one of F001-F012 is refuted by the amendment evidence. F006 and F007 are
valid findings with incomplete responses, and F008 is a valid finding carried as variation. There is
therefore no evidence-based reason to manufacture a decline for symmetry.

## 8. Verdict Vector

# `CONFORMS_WITH_GAPS`

| Dimension | Result | Named gap or basis |
| --- | --- | --- |
| Branch ancestry and allowed delta | **conforms** | All three heads are connector-confirmed ancestors; only the verification artifact is added on this stage. |
| Audit denominator and row arithmetic | **conforms with a minor rationale gap** | 16 is correct; amendment's discussion imprecisely associates F012 with the three consequential orientation errors although F012 is O-04. |
| One response per audit finding | **conforms** | 16 disposition rows and 16 verification results. |
| Registered disposition vocabulary | **gap** | Three invented tokens occupy a governed field. `accepted_corrected` is not one-to-one and hides F006/F007 variation. |
| Substantive audit closure | **gap** | F006 and F007 are partial; F008 remains intentionally open and honestly registered. |
| In-place/additive correction discipline | **conforms with F006 gap** | Correct in both directions except incomplete source-state repair. |
| Standing, union, non-substitution and institutional non-effect invariants | **conforms** | No authority, capability, owner or gate upgrade. |
| Terminal Git/remote transcript | **environmental coverage gap** | No checkout and DNS failure; this is an environmental limit in my verification, not a package defect. |

No blocker supports `NO_GO`: the union is not collapsed, the row-invariance rule remains, no authority
is minted, no standing axis is upgraded, and the open findings are bounded and visible. A clean
`CONFORMS` is unavailable because the disposition field violates the registered vocabulary and two
rows represented as corrected do not meet the audit's full closing conditions.

Required next action is bounded correction before consolidation or explicit consolidation treatment:

1. replace the 16 disposition cells with registered tokens using the verified 13/3/0 mapping;
2. complete or explicitly bound S01-S22 replay, especially the remaining mutable/under-located rows;
3. add a field-level vocabulary-owner status to the twelve ceiling dimensions;
4. retain F008 as `accepted_with_variation` / `semantic_test_missing` until the 63-case manifest and
   mutant failures exist; and
5. correct the denominator explanation so F012 is identified as O-04, separate from the three
   consequential orientation errors.

## 9. Receipt And Non-Effect

This verification changes no package, audit, amendment, source, workflow, `AGENTS.md` or pattern
register file. It adds only this Markdown verification artifact.

This stage does not:

- lift `GO_WITH_REVISIONS`;
- ratify any INT-R2 proposition;
- change any W4-K05 standing axis;
- close F008 by declaration;
- appoint a vocabulary owner, acquisition owner or institutional holder;
- classify the fourteen residuals;
- implement an evaluator, producer bridge, fixture battery or surface; or
- open a production/public-signature gate.

The final remote head and connector readback are reported in the stage hand-back after this file's
commit. Terminal Git outputs are reported verbatim as failed environmental receipts, not replaced by
connector values.