# INT-R6 Delta Verification Orientation Ledger

## Identity and connector evidence

This verifier authored none of the package, audit, amendment, stage-4 verification, or remediation.
All observations are connector observations.

- `GitHub.compare_commits`, remediation
  `eb9b135089d4a54b648973db02f0312b276ea2ea` → itself: merge base same,
  ahead `0`, behind `0`.
- `GitHub.compare_commits`, verification
  `1accee3534befa8ce9bc656a1b35f8eaca7e9b74` → remediation: merge base
  verification, ahead `3`, behind `0`.
- `GitHub.compare_commits`, base
  `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f` → remediation: merge base base,
  ahead `52`, behind `0`.
- `GitHub.create_branch`: `research/int-r6-delta-verification` from exact remediation SHA;
  `GitHub.fetch` exact ref confirmed the same SHA before writing.

## Supplied orientation versus measurement

| item | supplied | connector measurement | disposition |
|---|---|---|---|
| final net delta | 5 Markdown paths; 4M+1A; 287/154 | `compare_commits` verification→remediation returns exactly that set and aggregate | agree |
| intermediate report | 24/19 | verification→`569e07808439bbee121aacbb6dca1e36acfe5e15`: 24/19 | agree |
| corrected content report | 17/13 | verification→`be09f117d3de2fe3c50b59be6b84a109757e7fd5`: 17/13 | agree |
| correction effect | removes 7 additions and 6 deletions net | direct correction is 9/10; net report comparison changes 24/19 to 17/13 | agree, with whitespace qualification |
| receipt-only successor | only receipt ledger | `be09f117...`→`eb9b135...`: one file, remediation ledger, 42/12 | agree |
| predecessor population | 19 unique IDs | exact `fetch_file` at `b612b212...` finds F001–F019 | agree |
| literal successor identifiers | 4 | exact final baseline contains literal F001/F019 range endpoints plus explicit F002/F014 | agree |
| successor matrix | 19 rows | 16 baseline-claim rows + 3 predecessor-main rows | agree; row count alone is not closure |
| A05 exclusive split | 27 unallocated / 3 existing-only / 0 artifact / 0 lane | exact 30-row read gives same split | agree |
| stage-4 lift conditions | 5/9 | unchanged stage-4 artifact states 5/9 | agree |
| current lift conditions | not supplied | bounded retest gives 8/9 | verifier result |
| remediation subtree | `truncated:false`, 8 blobs | recursive tree `e18fd085...` reports exactly that | agree |

The direct correction removed every malformed substantive substitution. It also removed one blank
separator and normalized the final newline. I do not call that byte-exact restoration; I classify it
as semantically inert formatting because no Markdown block, proposition or locator was removed.

## A02 mapping method and result

Connector observation — `GitHub.fetch_file` at predecessor SHA
`b612b21272c732d53cfde8569846cfb7a0c73f5a` read both removed predecessors in full.
Connector observation — `GitHub.fetch_file` at remediation SHA
`eb9b135089d4a54b648973db02f0312b276ea2ea` read the complete successor baseline.

Method: enumerate predecessor headings F001–F019; for each, bind title, coordinate, original
method and denominator; then locate the successor row and supporting B-row/restored fact. Grouping
counts only where each member remains separately identifiable.

| ID | successor mapping | method/denominator custody | result |
|---|---|---|---|
| F001 | active-locale/D4 row | D4-A1 record plus named locale owners | restored |
| F002 | explicit stale-row/D4 row | 1 backlog row + 1 D4-A1 record | restored historical |
| F003 | active-locale row | named frontend/backend owners | restored |
| F004 | `locale_preference` row | 4 named producer/contract files | restored narrower |
| F005 | i18n-cohort + one-context rows | complete 18-blob cohort | restored bounded |
| F006 | catalogue blob row | 3 JSON / 3 files | restored |
| F007 | structural-parity row | named parity test | restored |
| F008 | DS0 row | 3-catalogue historical snapshot | retained historical |
| F009 | ICU/morphology row | named message/provider/parity files | restored |
| F010 | same ICU/morphology row | same files; grammatical-feature contract | restored |
| F011 | validity-ID/`limited` row | named status owners/validator | restored |
| F012 | same status-owner row | named scoped `limited` owners | restored |
| F013 | free-string denied-use row | 4 named owners/surfaces | restored |
| F014 | explicit adjacent-status row | 1 validator file outside closed set | restored bounded |
| F015 | trust-twin row | 1 named twin | restored |
| F016 | Lex/authority-relation row | 3 owner files + 6 corpus blobs | restored bounded |
| F017 | `SPOCandidate` pivot row | 1 named owner | restored |
| F018 | source-content/RTL row | named owners + bounded walks | restored as not established |
| F019 | same source-content/RTL row | D4-A1 + provider/direction evidence | restored unsupported |

Result: **19/19 mapped**. The grouped rows are F001/F003, F009/F010, F011/F012 and
F018/F019; F005 uses two complementary rows. Separately, the removed 139-line main file's task
boundary, false shell framing, and empty-headings claim families remain **3/3** restored or retracted.

## A05 count method

Connector observation — exact read of the 30 table rows in
`06-findings-standing-and-pattern-pass.md` at remediation SHA:

```text
explicit unallocated 27
specific existing identity anywhere 7
  mixed existing + unallocated 4
  existing-owner-only 3
artifact owner 0
generic work lane owner 0
exclusive total 27 + 3 = 30
```

The seven rows naming a specific existing identity are F001, F003, F006, F009, F023, F025 and
F026. F010 and F027 are explicit `unallocated`. No row creates an appointment.

## Orientation errors made and corrected

1. I initially treated “19 matrix rows” as a possible shortcut. Full predecessor reads showed that
   the matrix is 16 baseline rows plus three predecessor-main rows, so I performed semantic mapping.
2. I initially described the correction as exact restoration. Direct commit inspection exposed the
   removed blank separator and EOF normalization; I recorded that byte-level qualification while
   confirming no substantive content loss.
3. I initially treated the A05 categories as purely exclusive. Exact row reading showed seven
   existing-identity occurrences, four mixed with `unallocated`; both presence and exclusive counts
   are now reported.

## Recursive-tree discipline

- Connector observation — full-root recursive read at tree
  `f55efefd2b0a6936b3f92d5177d778dfd739695a` was response-clamped before
  GitHub's `truncated` value was observable; discarded from all denominators.
- Connector observation — recursive `int-r6` tree
  `e18fd085e565b8d4d826402f2b99c883b2b7a157` reported `truncated:false` and
  eight Markdown blobs.
- Traversal reads were non-recursive and carry no recursive denominator claim.
- No code-search result was used for a zero, positive, count or distribution.

## Connector receipts

The content commit carries both delta-verification artifacts. A receipt-only successor then changes
only this orientation ledger to record the immutable content-commit SHA and readback. A commit cannot
contain its own SHA; the final successor SHA is reported in the delivery hand-back.

```text
content_commit_sha: aa842d6293dc91df68272fdf3863a173be4eb474
content_tree_sha: 9c57724ab9536d8ef1836b95e33ba026235a503b
content_directory_tree_sha: a4604e5a48bb6d89ba191b3a572bcc1ed49ee5c9
content_directory_tree_truncated: false
```

Connector observation — `GitHub.fetch` exact branch ref resolved the content head to
`aa842d6293dc91df68272fdf3863a173be4eb474`. Connector observation —
`GitHub.fetch` recursive directory tree
`a4604e5a48bb6d89ba191b3a572bcc1ed49ee5c9` reported `truncated:false` and exactly
two Markdown blobs:

| artifact | blob SHA | bytes |
|---|---|---:|
| `int-r6-remediation-delta-verification.md` | `269d3b62b7bd190340a047385a460741d55cc031` | 8,400 |
| `int-r6-delta-verification-orientation-ledger.md` | `5b52986f3c5e6b90243c8aebdccb4fb301354928` | 7,303 |

Total content-head artifact size: **15,703 bytes**.

Connector observations — `GitHub.compare_commits` at the content head:

- remediation `eb9b135089d4a54b648973db02f0312b276ea2ea`: merge base same,
  ahead `1`, behind `0`; exactly two added Markdown paths, 257 additions / 0 deletions;
- verification `1accee3534befa8ce9bc656a1b35f8eaca7e9b74`: merge base same,
  ahead `4`, behind `0`;
- base `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`: merge base same,
  ahead `53`, behind `0`.

Connector observations — `GitHub.fetch_file` at exact content SHA read back both artifacts with
the blob identities above. Every content-head comparison had `merge_base_commit.sha` equal to the
stated base and `behind_by=0`.

This receipt-only successor changes only this orientation ledger. Its own SHA cannot be embedded
without changing the Git object; the final branch-head SHA is reported in the delivery hand-back.
