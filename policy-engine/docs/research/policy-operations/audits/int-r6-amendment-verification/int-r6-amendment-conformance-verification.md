# INT-R6 Amendment Conformance Verification

## Verification Identity And Pinned Evidence

Stage 4 verifies closure only. Repository reads were pinned to amendment SHA
`8137aa31a4bf5e06c6b1abd4e20458295fd5a506`; predecessor reads were pinned to
`b612b21272c732d53cfde8569846cfb7a0c73f5a`; audit criteria were pinned to
`bae4f8c2b5e5ef340dda73f17bfe852c1d0d3cee`.

Connector pre-write compares established:

| base | merge base | ahead | behind |
|---|---|---:|---:|
| amendment `8137aa31…` | `8137aa31…` | 0 | 0 |
| audit `bae4f8c2…` | `bae4f8c2…` | 10 | 0 |
| package `5e47c868…` | `5e47c868…` | 31 | 0 |
| base `dc7bdf79…` | `dc7bdf79…` | 42 | 0 |

For each row, `merge_base_commit.sha == base` and `behind_by == 0` is exactly
equivalent to `git merge-base --is-ancestor <base> <head>` exiting `0`.

## Verdict Vector

```yaml
verdict: NO_GO
delivery_and_containment: CONFORMS
disposition_reconciliation: CONFORMS
stage_contract_conformance: CONFORMS
finding_closure: 11_closed / 2_partially_closed / 1_not_closed
commendation_preservation: 4_of_4
preserve_properties: 12_of_12
lift_conditions: 5_of_9_satisfied
no_go_conditions: 1_of_11_triggered
disclosure_accuracy: stage_3_completion_disclosure_matches_branch
conditional_post_revision_GO: not_granted
```

The `NO_GO` is a research-quality verification result, not a W4-K05 standing.
The package standing remains:

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

## Architect Ground-Truth Recomputations

| ID | verifier result | disposition |
|---|---|---|
| G1 | audit→amendment 10 commits, package→amendment 31, base→amendment 42; every `behind_by=0` | agree |
| G2 | 9 paths: 8 modified package Markdown files and 1 added Markdown ledger; 0 audit/non-Markdown paths. Modified files total 1,459 additions/847 deletions; the ledger adds 202, so the complete 9-path aggregate is 1,661/847 | agree on paths and modified-file subtotal; disagree if 1,459/847 is presented as the whole 9-path aggregate |
| G3 | ledger blob `b43a0435a83f55b5250141620011d6aa7d9a4b20`, 202 lines, 20,165 bytes | agree |
| G4 | 14 unique audit rows; `1+6+3+4=14`; dispositions `13+1+0=14`; all disposition tokens are members of pipeline §3.3 | agree |
| G5 | original package: 8 files, 2,746 lines, 138,659 bytes; complete INT-R6 population at amendment SHA: 8 package + 1 ledger + 7 audit = 16 | agree |
| G6 | complete old/new eight-file walks: 3 non-member standing fields in the old main report and 0 in the amended eight-file package; main/scaffold point to the sole authority tuple in `06` | agree |
| G7 | package reports the supplied leaf/key/identity values, exact package SHA, 3 JSON/3 files, paths, executor and historical DS0 separation. The audit branch explicitly marks its own leaf/identity values `not_established`; the amendment harness aborts before parsing and Parser B calls `json.loads` | values match the architect-supplied figures, but the claimed auditor/author independent agreement is not earned |

## Finding Closure Register

| Finding | Severity | Claimed disposition | Audit closure criterion | Where the ledger says the change is | Where verifier found it | Closed? |
|---|---|---|---|---|---|---|
| IR6-A01 | blocking | `accepted` | no non-member standing fields or contradictory tuple in any carrying package artifact | main `421–458`; scaffold `21–27`; `06:2–101` | same ranges: main and scaffold explicitly delegate standing; `06` carries the registered tuple | `closed` |
| IR6-A02 | material | `accepted` | every deleted predecessor claim restored, retracted or recomputed with method/denominator | main `53–120`; `01:1–285` | `01:151–285` contains a 17-row grouped matrix, but predecessor findings `INT-R6-F002` and `INT-R6-F014` have no individual disposition | `partially_closed` |
| IR6-A03 | material | `accepted` | present capability claims changed to target-model language unless a real chain exists | main `121–455`; `03:201–356`; `04:1–617`; `05:231–419`; `06:2–169` | cited ranges distinguish research model/future contract from `absent/unallocated` capability | `closed` |
| IR6-A04 | material | `accepted` | executable current three-JSON census, attributable and independently cross-checked | main `53–105`; `01:1–200` | `01:31–145`: `sorted(...)` produces `en,ru,uk` but is asserted equal to `en,uk,ru`; Parser B also calls `json.loads` despite the contrary statement | `not_closed` |
| IR6-A05 | material | `accepted_with_variation` | all 30 F-rows identify an existing accountable owner or explicit `unallocated`; no lane-as-holder | `06:2–169` | 25 rows include `unallocated`; 3 owner-only rows name governing identities; F-010 and F-027 instead name the `INT-R6 research package`, which is an artifact, not an accountable owner in the governing owner vocabulary | `partially_closed` |
| IR6-A06 | material | `accepted` | repository fact, architecture demonstration and future behavior separated everywhere | main `121–455`; `03:201–356`; `04:1–220,441–617`; `05:231–419`; `06:2–169` | cited ranges label Ukraine/Phase 0 as architecture or target-contract behavior and preserve implementation absence | `closed` |
| IR6-A07 | material | `accepted` | certificate limited to exact tested population, purpose, residual and invalidators | main `121–411`; `02:1–335`; `04:1–452`; `05:1–230,394–419`; `06:2–169` | all cited artifacts state that one counterexample refutes and a finite pass proves only the declared population | `closed` |
| IR6-A08 | minor | `accepted` | dimensions/layers, not pairwise orthogonal coordinates; dependency edges explicit | main `4–47,190–260`; `03:1–220`; `04:108–175`; `06:2–75` | cited ranges bind `PresentationVariant` to parent proposition/version and optional parent rendition | `closed` |
| IR6-A09 | minor | `accepted` | SCC item `2117` and durable paragraph/article/section locators | main `482–522`; `02:1–80,290–335` | cited ranges use item `2117`, *Daoust* paragraphs 26–30, and primary-source spans | `closed` |
| IR6-A10 | minor | `accepted` | substantive entrypoint and retained scaffold role declared; eight files accounted | scaffold `1–27`; main `522–538` | cited ranges identify the scaffold as navigation/history and enumerate the original eight-file package | `closed` |
| IR6-C01 | commendation | `accepted` | preserve D4-A1 composition | main `4–50,455–485`; `03:1–25,201–356`; `04:1–60`; `05:231–255`; `06:2–101,150–169` | cited ranges retain `en` authored UI, `uk` translation, frozen `ru`, separate source rendering and unsupported RTL UI | `closed` |
| IR6-C02 | commendation | `accepted` | preserve three structural-parity-compatible red fixtures | main `341–411`; `04:221–370`; `05:1–230,394–419`; `06:150–169` | fixtures retain identical structural precondition and semantic red assertions | `closed` |
| IR6-C03 | commendation | `accepted` | preserve co-authentic sets and reject mandatory English legal pivot | main `25–47,112–150,190–260`; `02:1–85,141–165,245–335`; `03:25–47,260–330`; `04:31–60,190–220,330–350`; `05:150–175,390–419`; `06:2–75,130–169` | cited ranges retain peer authority members and purpose-limited English aids | `closed` |
| IR6-C04 | commendation | `accepted` | preserve role/appointment/decision separation and purpose-scoped zero-holder refusal | main `145–170,300–340,360–450`; `03:201–300`; `04:31–60,380–440,510–617`; `05:176–230,251–385`; `06:2–150` | cited ranges preserve zero appointments without default/self-appointed holder or global blocking | `closed` |

All 14 ledger location cells point to package material that actually changed; none relies on
the amendment ledger alone. Location accuracy does not cure the three substantive residues above.

## Verdict-Lift Conditions

| # | condition | result |
|---:|---|---|
| 1 | A01–A10 all closed | fail: A02 partial, A04 not closed, A05 partial |
| 2 | every fix appears in every defective artifact | fail: two predecessor claims remain undispositioned; two F-rows retain non-owner identities |
| 3 | current locale census independently executed and attributable | fail: published harness cannot reach its output and the claimed second parser is not independent |
| 4 | package remains research Markdown | pass |
| 5 | re-audit has zero blocking and zero material residues | fail: blocking A01 closed, but three material residues remain |
| 6 | one conforming W4 tuple, separate from audit verdict | pass: one package authority tuple; ledger metadata projection is byte-identical and non-authoritative |
| 7 | C01–C04 survive | pass |
| 8 | principal links and source spans resolve | pass within connector/source reach |
| 9 | complete inventory has no undeclared artifact or path regression | pass |

Result: **5/9 satisfied**. Conditional post-revision `GO` is not granted.

## NO_GO Conditions

| # | condition | result |
|---:|---|---|
| 1 | non-member/audit-verdict token remains in standing | not triggered |
| 2 | historical or supplied census is labelled current/recomputed | **triggered at artifact-evidence level**: current author execution is asserted, but the only published harness aborts before parsing and misstates parser independence |
| 3 | finite fixture pass is universal equivalence proof | not triggered |
| 4 | informative translation promoted by score/certificate/UI locale | not triggered |
| 5 | co-authentic law forced through English fallback | not triggered |
| 6 | parallel status/refusal lattice created | not triggered |
| 7 | vacant role silently passes, self-appoints or globally blocks | not triggered |
| 8 | generic work lane presented as owner | not triggered as worded; A05 separately fails because two rows present a document artifact as owner |
| 9 | correction exists only in amendment ledger | not triggered |
| 10 | unauthorized source/workflow/AGENTS/pattern/binary/staging edit | not triggered |
| 11 | ancestry or exact delta cannot be enumerated | not triggered |

Any one trigger forces the research-quality verdict `NO_GO`; condition 2 is triggered.
This does **not** establish that the supplied catalogue numbers are false. It establishes that the
amendment did not earn its claimed author-executed recomputation.

## Stage-Contract Conformance

Pipeline §2 branch topology conforms: verification descends append-only from the exact amendment
head. Pipeline §3.3 conforms: 14 rows reconcile to the 14-row audit register and every disposition is
one of `accepted`, `accepted_with_variation`, or `declined_with_reason`. The three headings-only
artifacts were created in separate commits before substantive writes.

Stage-contract conformance and substantive closure are separate dimensions. The ledger is formally
well-formed while A02, A04 and A05 remain incompletely closed.

## Findings And Residuals

- **V-R6-01 — material:** A02 recovery matrix accounts for 17/19 numbered predecessor baseline
  findings. `INT-R6-F002` (stale backlog-row disposition) and `INT-R6-F014` (adjacent open-string
  status fields) are not individually restored, retracted or recomputed.
- **V-R6-02 — material/NO_GO:** A04's published census harness cannot execute as written, and its
  claimed independent parser calls the same standard JSON decoder for every string.
- **V-R6-03 — material:** A05 resolves 28/30 rows. F-010 and F-027 name the research package itself
  as accountable owner; governing ownership records name human/logical owner groups, not documents.

## Connector Receipts

Content-commit and receipt-only successor observations are recorded in the final orientation ledger.
No shell transcript is asserted.
