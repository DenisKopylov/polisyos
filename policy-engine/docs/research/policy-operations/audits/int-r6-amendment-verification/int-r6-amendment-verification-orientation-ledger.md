# INT-R6 Amendment Verification Orientation Ledger

## Verification Identity And Branch Topology

Exact amendment ref read: `8137aa31a4bf5e06c6b1abd4e20458295fd5a506`.
The verification branch was created at exactly that SHA.

Pre-write connector comparisons:

| base | merge base | ahead | behind | containment |
|---|---|---:|---:|---|
| `8137aa31…` | `8137aa31…` | 0 | 0 | exact start |
| `bae4f8c2…` | `bae4f8c2…` | 10 | 0 | audit ancestor |
| `5e47c868…` | `5e47c868…` | 31 | 0 | package ancestor |
| `dc7bdf79…` | `dc7bdf79…` | 42 | 0 | base ancestor |

For each base `X`, equality of merge base to `X` with `behind_by=0` is exactly equivalent to
`git merge-base --is-ancestor X <verification-head>` exiting `0`.

## G1-G7 Recomputations

| ID | supplied | verifier measurement | agree? |
|---|---|---|---|
| G1 | 10 / 31 / 42 commits; zero behind | connector compares returned exactly 10 / 31 / 42 and zero behind | agree |
| G2 | 9 paths; 8 modified, 1 added; 1,459/847 | path/status facts agree. The 8 modified files total 1,459/847; adding the 202-line ledger makes the full 9-path aggregate 1,661/847 | qualified disagreement on aggregate label |
| G3 | ledger blob, 202 lines, 20,165 bytes | blob `b43a0435a83f55b5250141620011d6aa7d9a4b20`; 202 lines; 20,165 bytes | agree |
| G4 | 14 IDs; 13/1/0 dispositions; 1/6/3/4 severity | table-row count independently gives the same values; all disposition tokens are closed-vocabulary members | agree |
| G5 | 8 package files, 2,746 lines, 138,659 bytes; population 16 | independent per-blob sums and partitioned directory walks give the same values | agree |
| G6 | non-member standing fields 3→0 | complete old/new eight-file reads found the three old fields only in the old main report and none as fields in the amended eight files | agree |
| G7 | current values allegedly measured by architect, auditor and author | exact 3 JSON/3 files/blobs agree and package reports the supplied values. The audit artifact says its leaf/identity values are `not_established`; the author harness is non-executable and not parser-independent | disagree with three-way-agreement claim; reported numbers match architect values |

## Disclosure Accuracy

The Stage-3 **completion** disclosure matches the branch on the facts it reports:

- final amendment head `8137aa31a4bf5e06c6b1abd4e20458295fd5a506`;
- ledger blob `b43a0435a83f55b5250141620011d6aa7d9a4b20`;
- 202 lines / 20,165 bytes;
- 14 rows and both reconciliation sums;
- nine-path amendment population and complete 16-file INT-R6 population;
- *Daoust* item `2117`, paragraphs 26–30.

Earlier Stage-3 prose had reported a nonexistent ledger, population 16 before the ledger existed, and
paragraphs 26–31. The completion pass explicitly records and corrects those errors. Disclosure
accuracy is therefore `matches_branch_for_completion_pass`; historical overstatement is not used as
artifact credit or penalty.

## Tree And Inventory Measurements

Original package at amendment SHA:

| lines | bytes | artifact |
|---:|---:|---|
| 538 | 28,432 | `int-r6-multilingual-authority-equivalence-protocol.md` |
| 27 | 1,456 | `int-r6-multilingual-authority-equivalence.md` |
| 285 | 15,539 | `int-r6/01-repository-baseline.md` |
| 335 | 19,404 | `int-r6/02-external-evidence.md` |
| 356 | 15,883 | `int-r6/03-language-axis-partition.md` |
| 617 | 24,206 | `int-r6/04-multilingual-authority-equivalence-protocol.md` |
| 419 | 19,041 | `int-r6/05-red-first-fixtures-and-phased-deployment.md` |
| 169 | 14,698 | `int-r6/06-findings-standing-and-pattern-pass.md` |

Totals: **8 files / 2,746 lines / 138,659 bytes**.

Population derivation:

- two root package files from pinned policy-operations contents;
- `int-r6` subtree `769a35fe…`: seven blobs, `truncated:false` (six appendices + ledger);
- audit subtree `c2a455d9…`: seven blobs, `truncated:false`;
- total `2 + 7 + 7 = 16`.

All seven audit blob SHAs are byte-identical between audit and amendment heads:
`df9cd873…`, `a8740a0f…`, `fe57cf1d…`, `6ff1b295…`, `4d5edb0e…`,
`372f6037…`, `f1134768…`.

An oversized recursive policy-operations tree read was response-clamped before its `truncated` flag
was observable. It was discarded and supports no denominator. No code-search result was used for a
zero, positive, count or distribution.

## Orientation Errors Made And Corrected

1. I initially treated the ledger's “second parser” statement as potentially sufficient before
   reading the script. The script itself shows both a fatal filename-order assertion and a
   `json.loads` call inside Parser B.
2. I initially treated the successor matrix row count as evidence of full recovery. Enumerating the
   predecessor's 19 numbered findings exposed two undispositioned claims.
3. I initially accepted `1,459/847` as the complete nine-path delta. It is the eight-modified-file
   subtotal; the added 202-line ledger makes the complete aggregate `1,661/847`.
4. I initially repeated the supplied “three-way agreement” on catalogue values. The audit artifact
   itself records those leaf/identity values as `not_established` by the auditor.

## Residual Band

The connector did not materialize the three catalogue JSON payloads into an executable environment,
so this verifier did not independently recalculate leaf and identity values. That is an environment
limit. A04 fails for a separate artifact reason visible without execution: the published harness
cannot produce its claimed output.

External legal merits, Ukrainian wording quality, runtime behavior and cryptographic design were not
re-audited. Owner verification was bounded to the governing D4 record, logical ownership record and
repository CODEOWNERS.

## Connector Receipts

### Content-head receipt

Connector exact-ref read resolved the completed substantive verification content to:

```text
content_commit_sha: 080fd6f6c3a30742ea3f87a47b9a55c2eb9e42b9
```

At that SHA:

- amendment compare: merge base `8137aa31…`, ahead `6`, behind `0`, exactly three added
  Markdown files under `audits/int-r6-amendment-verification/`;
- audit compare: merge base `bae4f8c2…`, ahead `16`, behind `0`;
- package compare: merge base `5e47c868…`, ahead `37`, behind `0`;
- base compare: merge base `dc7bdf79…`, ahead `48`, behind `0`;
- verification subtree `db7a3b7da197c3db49f1d7cfcac5021e4b750303` reported
  `truncated:false` and exactly three blobs;
- substantive blob/byte set:
  - conformance `a50bc4fce416151563a6de2b1969866c22817bf2`, 11,745 bytes;
  - orientation `c86bdc0f668483ff9f2a21119e87b341312ce2d0`, 5,943 bytes;
  - preserve/recovery `a61ef6ac87ec8aa2420092cc4ac66913cd10dba9`, 6,861 bytes;
  - total `24,549` bytes.

Every comparison had `merge_base_commit.sha == stated base` and `behind_by == 0`.

### Receipt-only successor convention

This receipt-only commit records the immutable content-head SHA above. It cannot also contain its own
final SHA because embedding that value would change the Git object. The final branch-head SHA and the
four repeated final comparisons are therefore reported in the delivery hand-back and remain directly
readable from the exact branch ref.
