# INT-R6 Remediation Delta Verification

## Verification identity and verdict

Connector observation — `GitHub.compare_commits`, base/head
`eb9b135089d4a54b648973db02f0312b276ea2ea`: merge base equals the remediation
head, `ahead_by=0`, `behind_by=0`. Connector observation — the same operation from
stage-4 verification `1accee3534befa8ce9bc656a1b35f8eaca7e9b74` and base
`dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f` to the remediation head returned each
stated base as merge base and `behind_by=0`. Connector observation —
`GitHub.create_branch` created `research/int-r6-delta-verification` from exactly the
remediation head.

```yaml
verdict: CONFORMS_WITH_GAPS
delta_bounded: yes
finding_closure:
  IR6-A02: CLOSED
  IR6-A04: CLOSED
  IR6-A05: CLOSED
invariants_held: all_named_invariants
no_go_condition_cleared: yes
lift_conditions: 8_of_9_satisfied
stage_4_NO_GO_lifts: yes_to_CONFORMS_WITH_GAPS
remaining_gap: current_leaf_identity_census_not_independently_executed
```

This is a research-quality delta-verification verdict. It does not alter the W4-K05
standing:

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

## Delta bound and disclosed incident

Connector observation — `GitHub.compare_commits`, base
`1accee3534befa8ce9bc656a1b35f8eaca7e9b74`, head
`eb9b135089d4a54b648973db02f0312b276ea2ea`: exactly five Markdown paths, four
modified and one added, **287 insertions / 154 deletions**.

| status | path | net scope |
|---|---|---|
| M | `int-r6-multilingual-authority-equivalence-protocol.md` | A04 withdrawal |
| M | `int-r6/01-repository-baseline.md` | A04 withdrawal; A02 recovery |
| M | `int-r6/06-findings-standing-and-pattern-pass.md` | A04 evidence label; A05 ownership |
| M | `int-r6/amendment-ledger.md` | only A02/A04/A05 rows |
| A | `int-r6/remediation-ledger.md` | bounded remediation record and receipts |

Connector observations — `GitHub.compare_commits`:

| comparison | substantive-report additions/deletions | result |
|---|---:|---|
| verification → `569e07808439bbee121aacbb6dca1e36acfe5e15` | 24 / 19 | agrees with supplied incident measurement |
| verification → `be09f117d3de2fe3c50b59be6b84a109757e7fd5` | 17 / 13 | agrees; net removes 7 additions and 6 deletions |
| `569e07808439bbee121aacbb6dca1e36acfe5e15` → `be09f117d3de2fe3c50b59be6b84a109757e7fd5` | 9 / 10 | correction touched only the report and remediation ledger |
| `be09f117d3de2fe3c50b59be6b84a109757e7fd5` → remediation | 0 / 0 | receipt successor changed only remediation ledger |

Connector observation — `GitHub.fetch_commit` at `569e07808439bbee121aacbb6dca1e36acfe5e15`
found malformed out-of-scope substitutions in the report: a prose typo, corrupted diagram
glyphs, a grammar change, a duplicated pipeline step number, a damaged `C_test` token, and a
damaged Article 33 locator. Connector observation — `GitHub.fetch_commit` at
`be09f117d3de2fe3c50b59be6b84a109757e7fd5` restores each substantive line to the
verification-head wording. Its only additional report differences are removal of one blank
separator before `## External evidence` and end-of-file newline normalization. Those alter no
Markdown block, proposition, locator, or invariant; no pre-existing substantive content was
removed. Nothing malformed survives at the remediation head.

The final net changes in each modified file are confined to A02/A04/A05. The exact path set
contains no source, workflow, staging, binary, `AGENTS.md`, pattern-register, audit, or stage-4
verification path. The disclosed incident therefore does not make the semantic delta
unverifiable.

Connector observation — full-root recursive tree read at remediation tree
`f55efefd2b0a6936b3f92d5177d778dfd739695a` was connector-clamped before GitHub's
`truncated` value was observable; it was discarded from every denominator. Connector
observation — `GitHub.fetch` recursive tree
`e18fd085e565b8d4d826402f2b99c883b2b7a157` at the remediation head reported
`truncated:false` and exactly eight Markdown blobs in `int-r6/`. With the two root artifacts,
the package population is ten files. No code-search result settles a zero or positive.

## Three-finding retest

All package observations in this section are connector observations from `GitHub.fetch_file`
at exact remediation SHA `eb9b135089d4a54b648973db02f0312b276ea2ea`, except the
predecessor reads explicitly pinned to `b612b21272c732d53cfde8569846cfb7a0c73f5a`.

| finding | verdict | verification |
|---|---|---|
| `IR6-A04` | **CLOSED** | Terminal B is real withdrawal: author execution and parser independence are no longer asserted; the harness positive is absent; figures are `institutionally_supplied` and explicitly settle no zero; `3 JSON / 3 total files` remains a connector-observed denominator; “the catalogue census is now closed” is replaced by an open independent-execution limitation. W4-K03 is not engaged because no positive is preserved conditionally. |
| `IR6-A02` | **CLOSED** | Exact predecessor reads establish 19 unique F001–F019 findings. Claim-semantic mapping using title, coordinate, method and denominator maps all 19 to 16 baseline matrix rows; four rows legitimately group separately identifiable claims and F005 uses two rows. F002 and F014 now have explicit bounded restore dispositions. The three predecessor-main claim families remain separately 3/3 dispositioned. |
| `IR6-A05` | **CLOSED** | The 30-row denominator is intact. Exclusive owner-state split: 27 rows explicitly `unallocated`, 3 existing-owner-only, 0 artifact owners, 0 generic lanes. Seven rows name a specific existing identity somewhere; four of those are mixed with an explicit cross-cutting `unallocated` state. F010/F027 are unallocated; no appointment or invented owner appears. |

## Invariants

Connector observation — the final five-path compare, together with exact reads of the changed
artifacts and unchanged blob identities for the other package artifacts, gives:

| invariant | result | basis |
|---|---|---|
| A01 standing defect | **held** | one authoritative W4-K05 tuple in `06`; main/scaffold delegate to it; ledger projections are explicitly non-authoritative; no non-member field |
| C01 D4-A1 composition | **held** | `en` authored, `uk` translated, `ru` frozen; source rendering and RTL UI remain separate |
| C02 structural-parity red fixtures | **held** | fixture artifacts unchanged; report correction restores their original statement |
| C03 co-authentic/no mandatory English pivot | **held** | evidence, partition and protocol blobs unchanged; report wording restored |
| C04 role/appointment/decision separation | **held** | no owner or holder appointed; purpose-scoped zero-holder model unchanged |
| preserve properties 1–12 | **12/12 held** | D4, authority-set, status-ID, translation/adaptation, falsifier, zero-holder, append-only and external-evidence boundaries all remain |
| W4 standings | **held** | `accepted_narrow_scope / absent/unallocated / NO_GO` |
| other amendment-ledger rows | **11/11 untouched** | compare patch changes only A02, A04 and A05 |
| audit and stage-4 artifacts | **held byte-for-byte** | none appears in the exact final delta |

## Nine lift conditions

| # | condition | result |
|---:|---|---|
| 1 | A01–A10 closed | pass: A02/A04/A05 close here; the other seven remain held |
| 2 | every fix appears in every defective artifact | pass |
| 3 | current locale census independently executed and attributable | **gap**: Terminal B withdraws that positive; supplied values settle no zero |
| 4 | package remains research Markdown | pass |
| 5 | zero blocking and zero material residues after bounded retest | pass |
| 6 | one conforming W4 authority tuple, separate from audit verdict | pass |
| 7 | C01–C04 survive | pass |
| 8 | principal links and source spans resolve | pass: unchanged evidence artifacts; incident locator restored |
| 9 | complete inventory has no undeclared artifact/path regression | pass |

Result: **8/9**. The former NO_GO trigger—supplied numbers presented as an independently
recomputed current census—is cleared. The Stage-4 `NO_GO` therefore **lifts to
`CONFORMS_WITH_GAPS`**. The sole gap is the absence of an independently executed, attributable
current leaf/identity census; because the corresponding positive was withdrawn rather than
reasserted, that gap is not a NO_GO blocker.
