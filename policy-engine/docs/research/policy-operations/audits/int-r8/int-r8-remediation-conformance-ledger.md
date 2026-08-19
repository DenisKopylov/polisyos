---
title: "INT-R8 bounded-remediation conformance ledger"
verification_id: INT-R8-REMEDIATION-VERIFICATION
verified_commit: 286ade1057c9abb95bb1cf2c962479906f764667
verified_branch: research/int-r8-remediation
verification_branch: research/int-r8-remediation-verification
prior_verification_commit: ead4aca36f94d6014879c9f70b1074800c4ffabf
audited_commit: 90b372964d29a9e97605a6ef733ef03ffe7938d2
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
authoritative_for:
  - independent working evidence for delta-only verification of the INT-R8 bounded remediation
  - complete R4 unsafe-pass and R9 atomicity sweeps
  - denominator, deletion, discipline, and regression reconciliation
  - findings INT-R8-RV-001 through INT-R8-RV-008
may_not_use_for:
  - adoption amendment or ratification of INT-R8
  - production implementation authorization
  - final wire schema package database serialization or API contract
  - canonical owner appointment
  - authority grant capability claim or benchmark passage
  - legal sufficiency compliance or institutional competence conclusion
  - permission to publish a governed record
  - opening the first-public-record gate
  - automatic amendment of any plan or system-design decision
  - signature algorithm key policy rotation revocation or proof-construction selection
  - numerical disclosure bound or differently named scalar
research_only: true
---

# INT-R8 bounded-remediation conformance ledger

## 1. Scope and method

This verification answers only four questions: whether remediation closes R4, R5, R7, and R9;
whether the resulting suite denominators are correct everywhere they govern; whether the 34
removed lines are replacements rather than losses; and whether the remediation regression
statement remains true.

Ordinary GitHub DNS was unavailable. Repository reads, exact-ref comparisons, branch creation,
and ordinary Markdown commits used the connected GitHub interface. The manifest was delimited by
its fenced tables, not by a repository-wide line regex:

- red rows are the non-header lines between `## 3. Atomic red subfixtures` and its closing fence;
- green rows are the non-header lines between `## 4. Atomic green controls` and its closing fence;
- a valid row has exactly seven `|` separators, giving the declared eight fields; and
- fixture IDs are read only from the first field of those delimited rows.

This avoids counting prose such as “F01-F25 and G01-G05 remain family identities” as a fixture.
The local shell wrapper could not run without a checkout; the exact-ref table and comparison
operations were performed directly through the connector.

## 2. Geometry and binding

Exact comparison
`92b8773fe6da985b9803723d12c07233d6b90876...286ade1057c9abb95bb1cf2c962479906f764667`
returns:

| Quantity | Complete result |
|---|---:|
| commits ahead / behind | 3 / 0 |
| merge base | `92b8773fe6da985b9803723d12c07233d6b90876` |
| changed paths | 3/3 |
| modified / added | 2 / 1 |
| insertions / deletions | 280 / 34 |
| non-Markdown changed paths | 0/3 |

The paths are exactly:

1. `policy-engine/docs/research/policy-operations/int-r8/falsifier-suite-and-integration-handoff.md` — modified, +16/-5;
2. `policy-engine/docs/research/policy-operations/int-r8/amendment-ledger.md` — modified, +34/-29;
3. `policy-engine/docs/research/policy-operations/int-r8/remediation-ledger.md` — added, +230/-0.

The amendment branch still resolves exactly to the base SHA and the remediation branch exactly to
the verified SHA. All 3/3 changed artifacts are Markdown, retain non-empty `may_not_use_for` and
`research_only: true`, and carry the exact binding:

`remediated_after_verification: research/int-r8-amendment-verification@ead4aca36f94d6014879c9f70b1074800c4ffabf`.

## 3. Four-gap closure evidence

| Revision | Controlling proposition inspected | Independent determination |
|---|---|---|
| R4 | `falsifier-suite-and-integration-handoff.md:145-149,202-220`; unchanged formal dispositions at `reconstruction-composition-and-threat-model.md:153-235` | **conforms**. F21-D is an atomic empty-consistency fixture. F21-E is an atomic sampled-evaluator fixture. Both have eight typed fields and blocked loss outcomes. The complete 78-row sweep below contains no safe verdict inherited from an empty set, timeout, unsupported theory, sampled search, heuristic, posterior threshold, or unproved approximation. |
| R5 | suite `:180-197`; formal release-family split `reconstruction-composition-and-threat-model.md:109-151` | **conforms**. G05-B is neither silent completeness nor a full block: its loss outcome is `lossy_but_safe`, its reconstruction/completeness state is `external_history_not_established`, and its emitted proposition is expressly `bounded_to_declared_release_family`. |
| R7 | suite `:177-197`; materiality and procedure relations `semantic-contract-and-loss-boundary.md:132-251` | **conforms**. G04-B condenses two events while retaining both references, all three governed effect classes, and both order edges. The controlling relation requires every bound effect and order edge; dropping an effect invokes condensation/materiality failure and dropping an order edge invokes `compression_procedural_order_not_established`. |
| R9 | suite `:117-168` | **conforms**. F09-A, F09-B, and F09-C each mutate one independent collection or scalar. The complete red manifest has 71/71 eight-field, one-mutation rows with singleton or empty exact issue-code sets and no alternative expected values. |

## 4. Manifest denominator reconciliation

### 4.1 Red families and rows

The complete family distribution read from the red table is:

| Families | Per-family counts | Subtotal |
|---|---|---:|
| F01-F05 | 2, 3, 5, 1, 4 | 15 |
| F06-F10 | 4, 2, 2, 3, 2 | 13 |
| F11-F15 | 2, 1, 2, 2, 1 | 8 |
| F16-F20 | 1, 4, 3, 1, 3 | 12 |
| F21-F25 | 5, 2, 1, 2, 3 | 13 |
| F26-F30 | 2, 2, 2, 2, 2 | 10 |
| **Total** | **30 families** | **71 rows** |

Thus the exact denominators are **30/30 red families** and **71/71 red fixture rows**.
The arithmetic delta from the verified amendment is independently reproduced:

`67 - 1 bundled F09 row + 3 split F09 rows + 2 F21 rows = 71`.

### 4.2 Green families and rows

| Family | Controls |
|---|---:|
| G01 | 1 |
| G02 | 1 |
| G03 | 1 |
| G04 | 2 |
| G05 | 2 |
| **Total** | **7 rows across 5 families** |

Thus the exact denominators are **5/5 green families** and **7/7 green fixture rows**.
Total manifest rows are **71 + 7 = 78**.

### 4.3 Complete count-site walk

The exact-ref authoring universe is the primary report plus the seven files under `int-r8/`,
including the new remediation ledger: **8/8 artifacts read**. The five pre-remediation governing
count sites are all corrected:

| Site | Verified statement |
|---|---|
| suite red denominator, `falsifier-suite-and-integration-handoff.md:87-92` | 30/30 families, 71/71 red rows |
| suite green denominator, `:174-185` | 5/5 families, 7/7 controls |
| suite standing, `:264-270` | 71 red and 7 green |
| amendment-ledger R9 row, `amendment-ledger.md:56-74` | 30 red families, 71 red rows, 5 green families, 7 green rows |
| amendment-ledger `INT-R8-VI-001`, `:98-110` | same four quantities |

The remediation ledger's derivation, family blocks, sweeps, and entry-point summary consistently
use 30/71/5/7 and 78. No governing site retains “67 atomic red”, “67/67 mandatory”, “5 atomic
green”, or “5/5 atomic controls”.

The unrelated source census remains unchanged at
`orientation-ledger.md:108-132`:

`67 runtime + 12 scientist + 27 remainder = 106 distinct token-containing Python files`.

No blind substitution is visible.

## 5. Complete R9 atomicity sweep

Each manifest row below has eight fields, an exact loss outcome, an exact evaluation status, an
exact issue-code set, an exact affected-claim set, and an exact reconstruction status. “Atomic”
means one causal fixture mutation; coordinated representations of the same semantic mutation are
not treated as independent defects.

| Fixture | Mutation checked | Atomic | Typed fields | Loss outcome |
|---|---|---|---|---|
| F01-A | remove limitation L-1 as one semantic item | yes | 8/8 | blocked |
| F01-B | replace L-1 with generic limitation text | yes | 8/8 | blocked |
| F02-A | remove obligation-set reference | yes | 8/8 | blocked |
| F02-B | remove maintained-assumptions reference | yes | 8/8 | blocked |
| F02-C | remove relative-basis rider | yes | 8/8 | blocked |
| F03-A | map refusal to absence | yes | 8/8 | blocked |
| F03-B | map void to absence | yes | 8/8 | blocked |
| F03-C | map dispute to absence | yes | 8/8 | blocked |
| F03-D | map terminal-no-attempt to absence | yes | 8/8 | blocked |
| F03-E | map exhaustion to absence | yes | 8/8 | blocked |
| F04-A | emit one declared joint observation configuration | yes | 8/8 | blocked |
| F05-A | delete transformation reason | yes | 8/8 | blocked |
| F05-B | substitute noncanonical reason | yes | 8/8 | blocked |
| F05-C | mismatch scanner and reason | yes | 8/8 | blocked |
| F05-D | disclose protected value in explanation | yes | 8/8 | blocked |
| F06-A | remove first-attempt event | yes | 8/8 | blocked |
| F06-B | remove no-substitution event | yes | 8/8 | blocked |
| F06-C | remove sealing order edge | yes | 8/8 | blocked |
| F06-D | remove procedure package | yes | 8/8 | blocked |
| F07-A | delete denied use | yes | 8/8 | blocked |
| F07-B | weaken denied use to advice | yes | 8/8 | blocked |
| F08-A | delete dissent | yes | 8/8 | blocked |
| F08-B | replace dissent-qualified majority with consensus | yes | 8/8 | blocked |
| F09-A | remove rejected set only | yes | 8/8 | blocked |
| F09-B | remove conflict rows only | yes | 8/8 | blocked |
| F09-C | broaden consensus label only | yes | 8/8 | blocked |
| F10-A | delete visible limitation while pointer remains | yes | 8/8 | blocked |
| F10-B | delete visible counterevidence while pointer remains | yes | 8/8 | blocked |
| F11-A | publish deleted text in diff | yes | 8/8 | blocked |
| F11-B | publish identifying deletion index | yes | 8/8 | blocked |
| F12-A | publish low-entropy secret hash | yes | 8/8 | blocked |
| F13-A | retain private rank gap | yes | 8/8 | blocked |
| F13-B | publish identifying total count | yes | 8/8 | blocked |
| F14-A | publish identifying exact timestamp | yes | 8/8 | blocked |
| F14-B | delete custody chronology edge | yes | 8/8 | blocked |
| F15-A | reuse reviewer join key | yes | 8/8 | blocked |
| F16-A | make manifest self-disclosing | yes | 8/8 | blocked |
| F17-A | hide limitation in desktop CSS | yes | 8/8 | blocked |
| F17-B | clip rider in narrow viewport | yes | 8/8 | blocked |
| F17-C | hide denied uses in print | yes | 8/8 | blocked |
| F17-D | omit terminal from accessibility tree | yes | 8/8 | blocked |
| F18-A | add private PDF metadata | yes | 8/8 | blocked |
| F18-B | embed protected tracked change | yes | 8/8 | blocked |
| F18-C | retain raw-cell formula reference | yes | 8/8 | blocked |
| F19-A | add unrendered deep-link field | yes | 8/8 | blocked |
| F20-A | serve stale screenshot without head | yes | 8/8 | blocked |
| F20-B | export stale PDF without marker | yes | 8/8 | blocked |
| F20-C | return stale cached HTML | yes | 8/8 | blocked |
| F21-A | force exact-solver timeout | yes | 8/8 | blocked |
| F21-B | remove predicate package | yes | 8/8 | blocked |
| F21-C | remove item disposition | yes | 8/8 | blocked |
| F21-D | select empty consistency model | yes | 8/8 | blocked |
| F21-E | substitute unproved sampled evaluator | yes | 8/8 | blocked |
| F22-A | set receipt authority role | yes | 8/8 | blocked |
| F22-B | populate authoritative-for | yes | 8/8 | blocked |
| F23-A | reuse local pass without prefix check | yes | 8/8 | blocked |
| F24-A | delete controlled release member | yes | 8/8 | blocked |
| F24-B | narrow coalition after result | yes | 8/8 | blocked |
| F25-A | add epsilon | yes | 8/8 | blocked |
| F25-B | add cumulative percentage | yes | 8/8 | blocked |
| F25-C | add remaining budget | yes | 8/8 | blocked |
| F26-A | remove limitation in one locale | yes | 8/8 | blocked |
| F26-B | reuse translation-memory join key | yes | 8/8 | blocked |
| F27-A | omit rider in email | yes | 8/8 | blocked |
| F27-B | disclose identity in social metadata | yes | 8/8 | blocked |
| F28-A | expose gzip-length oracle | yes | 8/8 | blocked |
| F28-B | expose TLS-record oracle | yes | 8/8 | blocked |
| F29-A | expose existence through sitemap | yes | 8/8 | blocked |
| F29-B | expose category through autocomplete count | yes | 8/8 | blocked |
| F30-A | reuse proof key identifier | yes | 8/8 | blocked |
| F30-B | expose dissent through proof size | yes | 8/8 | blocked |

**Atomicity result: 71/71.** No expected-value field contains alternative issue codes,
`or`, `and/or`, a bare “Red”, or an unbound materiality premise.

## 6. Complete R4 unsafe-pass sweep

### 6.1 Red rows

All **71/71** red rows return `blocked_material_omission`. The target failure modes are explicit:

| Failure mode | Fixture or invariant | Result |
|---|---|---|
| empty consistency set | F21-D | `model_observation_inconsistent`; blocked |
| timeout | F21-A | `not_established_timeout`; blocked |
| unsupported theory | P13 plus unchanged formal outcome table | cannot pass |
| sampled search | F21-E | `not_established_unowned_approximation`; blocked |
| heuristic/classifier/posterior threshold | P13 plus unchanged no-hidden-estimator rule | cannot pass |
| any unproved approximation | F21-E and P13 | cannot pass |
| out-of-model channel | P13/P14 | cannot pass |

### 6.2 Green rows

| Fixture | Safe basis | Forbidden-mechanism dependency | Verdict |
|---|---|---|---|
| G01-A | exact declared-model non-reconstruction after duplicate citation condensation | none | valid green |
| G02-A | bound non-material identity replacement and exact non-reconstruction | none | valid green |
| G03-A | approved aggregate with exact declared-model non-reconstruction | none | valid green |
| G04-A | duplicate prose removed; constitutive events/order preserved | none | valid green |
| G04-B | two events faithfully condensed; effects/order preserved | none | valid green |
| G05-A | additional denied use with exact non-reconstruction | none | valid green |
| G05-B | bounded release-family proposition with external history not established | none; not a universal reconstruction claim | valid bounded green |

**Unsafe-pass result: 0/78 rows allow an empty set, timeout, unsupported theory, sampled search,
heuristic score, posterior threshold, or unproved approximation to inherit a safe verdict.**

## 7. R5 middle-position test

G05-B is distinguishable from both neighboring states:

| Neighbor | Distinguishing value |
|---|---|
| silently complete | G05-B records `external_history_not_established`, not `complete_for_declared_controlled_release_family`, and emits only `bounded_to_declared_release_family` |
| full block | G05-B retains `lossy_but_safe`, `evaluation_status=evaluated`, and an empty issue-code set for the bounded controlled-family proposition |

The fixture therefore demonstrates the intended limiting disposition rather than reusing the
already-tested blocking case or manufacturing universal completeness.

## 8. R7 positive-witness test

G04-B is nontrivial: two source events become one visible phrase. It remains green only because
both event references, three effect classes, and two order edges remain bound. The controlling
semantic relation states:

- every source item must retain a representative or be a proved duplicate;
- every bound effect must be preserved, otherwise condensation fails; and
- every required order relation must remain decidable, otherwise
  `compression_procedural_order_not_established` blocks.

Therefore dropping any of
`authority_or_status`, `contestability_or_recourse`, `history_or_currentness`,
`seal_before_adjudication`, or `adjudication_before_publication` changes the expected terminal
from green to blocked. The fixture is a discriminating positive witness, not an unconditional
“adjudication completed” pass.

## 9. Deletion classification

The complete 34-line deletion denominator is classified from the two modifying commit patches:

| File | Deleted lines | Classification | Replacement evidence |
|---|---:|---|---|
| suite | 5/5 | in-place replacement | old 67 denominator -> 71; bundled F09 row -> three atomic rows; old 5-control denominator -> 7; old closing 67/5 statement -> 71/7 |
| amendment ledger | 29/29 | in-place accountability/evidence replacement | prior pending-verification paragraph and old R4/R5/R7/R9/count evidence rows are replaced with remediation-pending text, new fixture anchors, and new denominators |
| **Total** | **34/34** | **replacement; lost = 0** | no family, fixture purpose, reason code, issue code, or commendation-backed proposition is removed |

The F09 `compression_consensus_overstated` result survives in F09-C; the split adds exact
counterevidence codes for F09-A/B rather than deleting the old semantic target.

## 10. Rewrite-discipline check

No appended “remediation section” was added to the suite or amendment ledger. Their controlling
rows and denominator statements were changed in place. `remediation-ledger.md` is the separately
required accountability record and does not supersede a competing governing fixture table. The
working documents therefore have one controlling manifest and one controlling amendment
register; history remains at immutable earlier commits.

Result: **no superseding-section reachability defect**.

## 11. Regression statement verification

### 11.1 Nine previously conforming revisions

The remediation statement contains **9/9** rows. Five supporting artifacts were unchanged by the
3-path diff; touched-suite dependencies were checked directly.

| Revision | Regression check | Result |
|---|---|---|
| R1 | capability table remains at suite `:219-236`; accountant remains “not a missing capability” | intact |
| R2 | orientation evidence path resolves; orientation file is unchanged | intact |
| R3 | primary/source/formal evidence paths resolve; all three files are unchanged | intact |
| R6 | F26-F30 remain at suite `:159-168`; open registry source unchanged | intact |
| R8 | F05 remains atomic at suite `:108-111`; semantic relation unchanged | intact |
| R10 | suite semantic handshake remains at `:238-249`; primary/semantic/formal files unchanged | intact |
| R11 | orientation invocation census path resolves; file unchanged | intact |
| R12 | external-source custody path resolves; file unchanged | intact |
| R13 | orientation and semantic limitation-carrier paths resolve; both unchanged | intact |

### 11.2 Nineteen commendations

The remediation statement contains **19/19** audit commendations. The cited evidence resolves at
the remediation head. Suite-dependent strengths were checked directly; all others remain in
unchanged blobs.

| Finding | Preserved strength | Result |
|---|---|---|
| INT-R8-I-001 | file-size/audience orientation | intact |
| INT-R8-I-003 | 67/12/27 = 106 file census | intact |
| INT-R8-I-005 | narrow named-token absence | intact |
| INT-R8-II-001 | public-administration source grounding | intact |
| INT-R8-II-004 | DP non-transfer plus open deterministic-QIF path | intact |
| INT-R8-III-001 | refusal of current canonical scalar | intact |
| INT-R8-III-003 | exact non-uniqueness remains Boolean | intact; R4 fixtures strengthen boundary |
| INT-R8-III-005 | adaptive actual-prefix induction | intact |
| INT-R8-IV-001 | conditional consistency-set/coalition definition | intact |
| INT-R8-IV-004 | broad open channel registry | intact |
| INT-R8-V-001 | categorical delta/negative terminals | intact |
| INT-R8-V-005 | reuse-first projection-only receipt | intact |
| INT-R8-VI-002 | F04/F12/F19/F24/F25 and all five green purposes | intact; two witnesses added |
| INT-R8-VII-001 | ratified findings applied in confirmed direction | intact |
| INT-R8-VII-002 | K04/K07-compatible Boolean prefix discipline | intact |
| INT-R8-VIII-001 | content/proof boundary | intact |
| INT-R8-IX-002 | existing projection/export substrate visible | intact |
| INT-R8-X-001 | research and non-use prohibitions | intact; 3/3 touched files bound to verification |
| INT-R8-X-002 | `accepted_narrow_scope` substantive target | intact; first-public gate remains closed |

Regression denominators: **9/9 revisions** and **19/19 commendations**.

## 12. Working finding register

| Finding ID | Severity | Determination |
|---|---|---|
| INT-R8-RV-001 | commendation | Geometry, Markdown-only scope, merge base, exact refs, and remediation bindings reproduce. |
| INT-R8-RV-002 | commendation | R4 is closed: F21-D/E are exact and 0/78 rows permit an unsafe approximation to inherit safety. |
| INT-R8-RV-003 | commendation | R5 is closed: G05-B is a genuine limiting, non-complete, non-blocking result. |
| INT-R8-RV-004 | commendation | R7 is closed: G04-B is a discriminating faithful-condensation witness. |
| INT-R8-RV-005 | commendation | R9 is closed: F09 is split and 71/71 red rows satisfy atomicity. |
| INT-R8-RV-006 | commendation | The 30/71/5/7/78 denominators are consistent and the unrelated 67/12/27 census is untouched. |
| INT-R8-RV-007 | commendation | All 34 deletions are replacements and no superseding-section pattern was introduced. |
| INT-R8-RV-008 | commendation | The regression statement resolves 9/9 conforming revisions and 19/19 commendations. |

Count: **0 blocking, 0 material, 0 minor, 8 commendations = 8 findings**.

## 13. Working conclusion

All four delta gaps are closed in controlling text. The audit's gate—R1 through R10 executed and
independently verified—is now met. `accepted_narrow_scope` may be carried into consolidation.
This does not open the first-public-record gate and authorizes no implementation, publication,
owner, proof construction, legal conclusion, or numerical disclosure bound.
