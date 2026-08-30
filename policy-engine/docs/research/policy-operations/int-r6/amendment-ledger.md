# INT-R6 Stage 3 amendment ledger

## Scope and standing

This is the recording-only completion of the Stage-3 amendment. It adds no research finding,
changes no conclusion, appoints no holder, implements no capability, and opens no gate.

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

`GO_WITH_REVISIONS` is the Stage-2 audit verdict, not a standing value.

## Re-derived audit register

Connector observation — `GitHub.fetch_file`, audit SHA
`bae4f8c2b5e5ef340dda73f17bfe852c1d0d3cee`,
`audits/int-r6/int-r6-independent-audit.md`: the Finding Register has **14 table rows and
14 unique IDs**: `IR6-A01`–`IR6-A10` and `IR6-C01`–`IR6-C04`.

```text
blocking 1 + material 6 + minor 3 + commendation 4 = 14
```

This denominator is derived from table rows, not token occurrences.

## Architect-ground-truth recomputation

| Item | My recomputed value | Agreement |
|---|---|---|
| G1 — containment | `audit..amendment = 8`, `package..amendment = 29`, `base..amendment = 40`; all three `behind_by = 0`; each `merge_base_commit.sha` equals its stated base | agree |
| G2 — amendment delta | 8 modified files, 0 added, 0 deleted; all 8 are Markdown package files; 0 audit files touched; 1,459 insertions / 847 deletions | agree |
| G3 — package inventory | 8 files, 2,746 lines, 138,659 bytes; per-file values appear in the inventory below | agree |
| G4 — audit register | 14 unique rows: A01–A10 and C01–C04; `1 + 6 + 3 + 4 = 14` | agree |
| G5 — spot checks | non-member standing fields: `3 → 0`; exact-file scan of `06` found `unallocated: 2 → 44` while the F-row denominator stays 30; `Daoust` changed from `2004 SCC 6` to `2004 SCC 6, paragraphs 26–30`, SCC item `2117` | agree with the architect’s artifact counts; disagree with my prior hand-back’s `26–31` wording |

The source-supported shared-meaning span is **paragraphs 26–30**. Paragraph 31 begins the application
that follows the stated method; the package’s `26–30` wording is retained.

## Disposition ledger

| Finding | Severity | Disposition | Audit anchor | Every package artifact and line range changed | What is now true |
|---|---|---|---|---|---|
| IR6-A01 | blocking | accepted | `int-r6-independent-audit.md#finding-register`; recommended revision A01 | `int-r6-multilingual-authority-equivalence-protocol.md:421–458`; `int-r6-multilingual-authority-equivalence.md:21–27`; `int-r6/06-findings-standing-and-pattern-pass.md:2–101` | The package publishes one registered W4-K05 tuple. The former `evidence_standing`, `decision_standing`, and `implementation_standing` fields are absent; the audit verdict is not used as standing. |
| IR6-A02 | material | accepted | audit A02; recommended revision “Standing and evidence custody” | `int-r6-multilingual-authority-equivalence-protocol.md:53–120`; `int-r6/01-repository-baseline.md:1–285` | Every substantive predecessor claim is restored, recomputed, retained as historical, or retracted in a predecessor→successor matrix with method and denominator. Filename succession alone carries no evidentiary effect. |
| IR6-A03 | material | accepted | audit A03; recommended revision “Capability and claim orientation” | `int-r6-multilingual-authority-equivalence-protocol.md:121–455`; `int-r6/03-language-axis-partition.md:201–356`; `int-r6/04-multilingual-authority-equivalence-protocol.md:1–617`; `int-r6/05-red-first-fixtures-and-phased-deployment.md:231–419`; `int-r6/06-findings-standing-and-pattern-pass.md:2–169` | Present repository capability is no longer inferred from Markdown. Current capability remains `absent/unallocated`; target behaviour is written as proposed/future/modelled unless repository coordinates establish it. |
| IR6-A04 | material | accepted | audit A04; recommended revision “Catalogue census” | `int-r6-multilingual-authority-equivalence-protocol.md:53–105`; `int-r6/01-repository-baseline.md:1–200` | The current census is attributed to the Stage-3 author at package SHA, covers exactly 3 JSON/3 files, publishes the script, two independently implemented parsers, leaf/key/identity counts, and unequal denominators. DS0 remains historical. |
| IR6-A05 | material | accepted_with_variation | audit A05; recommended revision “Ownership” | `int-r6/06-findings-standing-and-pattern-pass.md:2–169` | All 30 F-rows now state an existing accountable identity or explicit `unallocated`, with scope and next action; 0/30 use a generic work lane as owner. Variation: the amendment records unallocation where no competent appointment exists and does not manufacture or appoint a holder. |
| IR6-A06 | material | accepted | audit A06; recommended revision “Capability and claim orientation” | `int-r6-multilingual-authority-equivalence-protocol.md:121–455`; `int-r6/03-language-axis-partition.md:201–356`; `int-r6/04-multilingual-authority-equivalence-protocol.md:1–220,441–617`; `int-r6/05-red-first-fixtures-and-phased-deployment.md:231–419`; `int-r6/06-findings-standing-and-pattern-pass.md:2–169` | Repository facts, architecture demonstrations, target-contract behaviour, and future implementation are explicitly separated. The Ukraine scenario and Phase 0 no longer imply a live runtime chain. |
| IR6-A07 | material | accepted | audit A07; recommended revision “Proof strength” | `int-r6-multilingual-authority-equivalence-protocol.md:121–411`; `int-r6/02-external-evidence.md:1–335`; `int-r6/04-multilingual-authority-equivalence-protocol.md:1–452`; `int-r6/05-red-first-fixtures-and-phased-deployment.md:1–230,394–419`; `int-r6/06-findings-standing-and-pattern-pass.md:2–169` | A counterexample refutes within the governed purpose; a finite passing suite establishes only a versioned, population-bounded result. Certificates bind digests, purpose, complete denominator, exclusions, reviewer basis, residual, and invalidators. |
| IR6-A08 | minor | accepted | audit A08; recommended revision “Architecture/citations/entrypoint” | `int-r6-multilingual-authority-equivalence-protocol.md:4–47,190–260`; `int-r6/03-language-axis-partition.md:1–220`; `int-r6/04-multilingual-authority-equivalence-protocol.md:108–175`; `int-r6/06-findings-standing-and-pattern-pass.md:2–75` | The five items are dimensions/layers with explicit dependency edges, not pairwise-orthogonal coordinates. `PresentationVariant` binds parent proposition/version and, where applicable, parent rendition and transformation chain. |
| IR6-A09 | minor | accepted | audit A09; recommended revision “Architecture/citations/entrypoint” | `int-r6-multilingual-authority-equivalence-protocol.md:482–522`; `int-r6/02-external-evidence.md:1–80,290–335` | The primary SCC locator is item `2117`; the shared-meaning method is anchored to paragraphs 26–30. Other load-bearing sources carry article, section, paragraph, clause, or model locators without replacing primary sources with summaries. |
| IR6-A10 | minor | accepted | audit A10; recommended revision “Architecture/citations/entrypoint” | `int-r6-multilingual-authority-equivalence.md:1–27`; `int-r6-multilingual-authority-equivalence-protocol.md:522–538` | The former 21-line headings scaffold is retained as navigation and delivery history, identifies the substantive report, and is not an independent standing record. The original eight-file package is explicitly inventoried. |
| IR6-C01 | commendation | accepted | audit C01; recommended revision C01 | `int-r6-multilingual-authority-equivalence-protocol.md:4–50,455–485`; `int-r6/03-language-axis-partition.md:1–25,201–356`; `int-r6/04-multilingual-authority-equivalence-protocol.md:1–60`; `int-r6/05-red-first-fixtures-and-phased-deployment.md:231–255`; `int-r6/06-findings-standing-and-pattern-pass.md:2–101,150–169` | D4-A1 composition is preserved: `en` authored UI, `uk` translation, `ru` frozen; source-content authority and RTL admission remain separate. |
| IR6-C02 | commendation | accepted | audit C02; recommended revision C02 | `int-r6-multilingual-authority-equivalence-protocol.md:341–411`; `int-r6/04-multilingual-authority-equivalence-protocol.md:221–370`; `int-r6/05-red-first-fixtures-and-phased-deployment.md:1–230,394–419`; `int-r6/06-findings-standing-and-pattern-pass.md:150–169` | The three binding falsifiers remain structurally parity-compatible and red-first; defects are semantic rather than missing-key failures. |
| IR6-C03 | commendation | accepted | audit C03; recommended revision C03 | `int-r6-multilingual-authority-equivalence-protocol.md:25–47,112–150,190–260`; `int-r6/02-external-evidence.md:1–85,141–165,245–335`; `int-r6/03-language-axis-partition.md:25–47,260–330`; `int-r6/04-multilingual-authority-equivalence-protocol.md:31–60,190–220,330–350`; `int-r6/05-red-first-fixtures-and-phased-deployment.md:150–175,390–419`; `int-r6/06-findings-standing-and-pattern-pass.md:2–75,130–169` | Co-authentic members remain peers under jurisdiction-specific rules; English may support UI/indexing/informative uses but is not a mandatory legal pivot or authority selector. |
| IR6-C04 | commendation | accepted | audit C04; recommended revision C04 | `int-r6-multilingual-authority-equivalence-protocol.md:145–170,300–340,360–450`; `int-r6/03-language-axis-partition.md:201–300`; `int-r6/04-multilingual-authority-equivalence-protocol.md:31–60,380–440,510–617`; `int-r6/05-red-first-fixtures-and-phased-deployment.md:176–230,251–385`; `int-r6/06-findings-standing-and-pattern-pass.md:2–150` | Role definition, appointment, and decision remain separate. Zero eligible holders produce only a modelled purpose-scoped refusal; no commission, default approver, or synthetic holder is invented, and unrelated functions require their own proof. |

### Reconciliation arithmetic

```text
accepted 13
accepted_with_variation 1
declined_with_reason 0
total dispositions 14
```

```text
blocking 1
material 6
minor 3
commendation 4
total severities 14
```

## Twelve preserved properties

| # | Required preserved property | Evidence in the amended package | Check |
|---:|---|---|---|
| 1 | D4-A1 unchanged: `en` authored UI, `uk` translation, `ru` frozen; source rendering separate; RTL UI unsupported | main `4–50,455–485`; partition `13–25,201–356`; findings `75–98` | preserved |
| 2 | UI locale never selects legal authority | main `190–210`; partition `13–25`; protocol `31–48,190–220` | preserved |
| 3 | Authority attaches to versioned jurisdictional text/member/set | external evidence `20–85`; partition `25–47,145–200`; protocol `190–220` | preserved |
| 4 | Co-authentic peers remain peers absent jurisdictional precedence | external evidence `38–85,141–145`; partition `260–286`; protocol `202–220,340–350` | preserved |
| 5 | English may aid UI/indexing but is not universal legal authority | main `25–47,241–260`; partition `287–330`; findings `55–72` | preserved |
| 6 | Existing namespaced status/refusal owners are reused | partition `35–47,113–142`; protocol `221–240`; findings `3–68` | preserved |
| 7 | `stale`, `superseded`, `withdrawn` remain distinct in human and machine projections | main `143–151,383–411`; external evidence `204–235`; protocol `326–370`; fixtures `108–145` | preserved |
| 8 | Translation and adaptation remain separate decisions | main `151–157,320–340`; external evidence `223–244`; protocol `371–398`; fixtures `166–175` | preserved |
| 9 | Three falsifiers remain red-first beyond parity | main `341–411`; protocol `260–370`; fixtures `1–145` | preserved |
| 10 | Zero holders remain representable and block only the governed purpose | main `145–170,300–340`; partition `241–286`; protocol `399–440`; fixtures `287–385` | preserved |
| 11 | History is append-only; invalidation does not rewrite it | protocol `31–60,492–525`; fixtures `360–385`; main `421–450` | preserved |
| 12 | External practice remains evidence, not repository capability | main `112–121`; external evidence `1–22`; protocol `1–15`; findings `100–128` | preserved |

None of the fourteen dispositions required weakening a preserved property.

## Eleven NO_GO-condition self-checks

1. **Standing tokens:** not triggered — all package standing projections use only the registered three-axis tuple; no audit-verdict token is a standing.
2. **Historical/supplied census labelled current:** not triggered — DS0 is historical; the current census names its executor, SHA, files, script, and denominator.
3. **Finite fixtures represented as universal proof:** not triggered — positive semantics are explicitly population-bounded with exclusions and residual.
4. **Informative translation promoted by score/certificate/UI locale:** not triggered — authority remains attached to jurisdictional source/member/set.
5. **Co-authentic law forced through English fallback:** not triggered — co-authentic members remain peers and divergence invokes the jurisdiction’s rule.
6. **Parallel status/refusal lattice created:** not triggered — examples must map to existing owners or remain vocabulary gaps/unallocated.
7. **Vacant role silently passes, self-appoints, or globally blocks:** not triggered — zero-holder state is purpose-scoped and no appointment is created.
8. **Generic lane presented as owner:** not triggered — 30/30 F-rows name an existing identity or `unallocated`; 0/30 use a lane as holder.
9. **Correction exists only in this ledger:** not triggered — every accepted correction is located above in the package artifacts that carried it.
10. **Unauthorized non-document edit:** not triggered — the amendment delta contains only eight package Markdown modifications; audit/source/workflow/`AGENTS.md`/pattern/binary/staging paths are unchanged.
11. **Ancestry or exact delta cannot be enumerated:** not triggered — connector comparisons and the exact eight-file delta are recorded below.

## Complete original eight-file inventory at amendment head

| Lines | Bytes | Blob SHA at `d782b95c…` | Artifact | Role |
|---:|---:|---|---|---|
| 538 | 28,432 | `e43cef7fef428cabf9a836d48e1127aaa433bc05` | `int-r6-multilingual-authority-equivalence-protocol.md` | substantive reader-facing research report |
| 27 | 1,456 | `93ece13470c569a2b44bd3ffae7a891a312c765e` | `int-r6-multilingual-authority-equivalence.md` | retained former headings scaffold; navigation and delivery-history entrypoint, not substantive report or standing authority |
| 285 | 15,539 | `08a69f3194b46a51f6a8b31daa70e2f34c046d08` | `int-r6/01-repository-baseline.md` | current census, restored bounded observations, predecessor→successor claim matrix |
| 335 | 19,404 | `7fac860086bc7dde7bdc2fb115642abd148367b4` | `int-r6/02-external-evidence.md` | external-evidence synthesis and durable source spans |
| 356 | 15,883 | `1133b208489ee6252e8499cff1230f79b829feb5` | `int-r6/03-language-axis-partition.md` | five dimensions, dependencies, fixtures, D4-A1 composition |
| 617 | 24,206 | `0443cb61dc170df2133ac67fa8797e7d861c28fd` | `int-r6/04-multilingual-authority-equivalence-protocol.md` | bounded target protocol specification; no implementation claim |
| 419 | 19,041 | `753b55713d2cabd82782f0ebcce0ee5f0801e640` | `int-r6/05-red-first-fixtures-and-phased-deployment.md` | red-first fixtures, proof boundary, phased and zero-holder model |
| 169 | 14,698 | `28c277d7e35e23a995bf17bdbfce7d1c546687e2` | `int-r6/06-findings-standing-and-pattern-pass.md` | 30-row owner-state register, single standing tuple, residuals, Pattern Pass |

```text
8 files
2,746 lines
138,659 bytes
```

This ledger is a ninth package/amendment artifact justified by pipeline §3.3; it does not alter the
identity or count of the original eight Stage-1 package artifacts.

## Connector receipts

### Pre-write observations

- `GitHub.fetch` exact ref `refs/heads/research/int-r6-amendment` read
  `d782b95c796975a3cf658f63037c8c938d5ec3e4`.
- `GitHub.compare_commits(base=d782b95c…, head=d782b95c…)` returned
  `merge_base_commit.sha=d782b95c…`, `ahead_by=0`, `behind_by=0`.
- `GitHub.compare_commits(base=bae4f8c2…, head=d782b95c…)` returned
  `merge_base_commit.sha=bae4f8c2…`, `ahead_by=8`, `behind_by=0`.
- `GitHub.compare_commits(base=5e47c868…, head=d782b95c…)` returned
  `merge_base_commit.sha=5e47c868…`, `ahead_by=29`, `behind_by=0`.
- `GitHub.compare_commits(base=dc7bdf79…, head=d782b95c…)` returned
  `merge_base_commit.sha=dc7bdf79…`, `ahead_by=40`, `behind_by=0`.
- For each base `X` and head `Y`, connector `compare(base=X, head=Y)` returning
  `merge_base_commit.sha == X` and `behind_by == 0` is exactly equivalent to
  `git merge-base --is-ancestor X Y` exiting `0`.
- `GitHub.fetch` recursive tree read of the full repository tree at `d782b95c…` was response-clamped
  before its `truncated` field became observable. That read was **discarded** and supports no
  denominator.
- `GitHub.fetch` recursive package-subtree read
  `79014ac20e75b4acfecddce92fadd1ab00cdac17` reported `truncated:false` and six numbered
  Markdown blobs. Pinned contents reads supplied the two root package files, giving the complete
  eight-file package denominator.
- `GitHub.fetch` recursive audit-subtree read
  `c2a455d9c1751264ab84ed6492aff7d9bbecc86c` reported `truncated:false` and seven audit
  Markdown blobs.
- No code-search result was used to establish a zero, a positive, or a set denominator.

### Post-write receipt subject

The post-write connector observations are appended below in the receipt-only successor commit.

`LEDGER_PAYLOAD_HEAD_SHA`
`LEDGER_PAYLOAD_BLOB_SHA`
`POST_WRITE_COMPARE_RECEIPTS`

A commit cannot embed its own SHA because changing the embedded value changes the Git object.
Accordingly, the exact SHA recorded here is the **receipt subject**: the complete ledger-content
commit immediately preceding the receipt-only successor. The exact successor branch-head SHA is also
reported by the connector in the delivery hand-back and remains directly readable in branch history.

## Orientation errors I made and corrected

- I reported an amendment ledger that did not exist. This file supplies the missing contract artifact.
- I reported an INT-R6 population of 16 files when the branch actually contained 15: eight package
  files and seven audit files. After this ledger is added, the reachable population becomes 16.
- I linked to `int-r6/amendment-ledger.md` before that file existed.
- I reported the *Daoust* span as paragraphs 26–31 while the amended artifacts and source support
  paragraphs 26–30. The package’s 26–30 locator is retained.

## Closure statement

All 14 audit rows have a closed-vocabulary disposition; disposition and severity sums each close at
14; every accepted correction is located in the package artifact(s) that carried it; all twelve
preserve-properties and eleven NO_GO conditions are checked; the original eight-file inventory is
complete; and no research conclusion or standing is changed.
