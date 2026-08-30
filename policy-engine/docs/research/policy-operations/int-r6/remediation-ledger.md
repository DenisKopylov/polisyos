# INT-R6 Stage 5 bounded-remediation ledger

## Orientation and authority boundary

This Stage-5 pass is bounded to `IR6-A02`, `IR6-A04`, and `IR6-A05`. It does not revisit the closed
blocking finding, any commendation, any preserve-property, or any other audit row. It does not issue
a replacement verification verdict.

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

This ledger issues no Stage-5 verdict. A fresh delta verifier is required for any change to the prior
verification result.

Pinned lineage:

| role | SHA |
|---|---|
| base | `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f` |
| audit | `bae4f8c2b5e5ef340dda73f17bfe852c1d0d3cee` |
| amendment | `8137aa31a4bf5e06c6b1abd4e20458295fd5a506` |
| verification head / remediation parent | `1accee3534befa8ce9bc656a1b35f8eaca7e9b74` |

The two Stage-4 ground-truth corrections govern this remediation:

- audit→amendment is **1,661 insertions / 847 deletions across 9 paths**; `1,459 / 847` is only the
  eight-modified-package-file subtotal before the 202-line ledger is included;
- there is no architect/auditor/author three-way independent catalogue measurement. The architect
  values are `institutionally_supplied`; the audit records its values as `not_established` and the
  Stage-3 harness did not execute.

## Bounded findings

### IR6-A04 — Terminal B: withdraw the execution positive

**Stage-4 defect.** The published harness asserts the sorted file sequence `en,uk,ru`, although
`sorted()` produces `en,ru,uk`, so it raises before reading a catalogue. Parser B also delegates each
string to `json.loads` while the appendix says it does not.

**Remediation.** Terminal B is used. The package removes the author-execution and independent-parser
assertions and does not publish a replacement harness positive. The architect-supplied catalogue
values remain labelled `institutionally_supplied` under W4-K01. The exact three paths, three JSON files, and three
total files remain connector-observed denominators; the supplied leaf/identity figures settle no
zero.

**Carrying locations.** `int-r6-multilingual-authority-equivalence-protocol.md:50–108`,
`int-r6/01-repository-baseline.md:7–62,183–195`, and
`int-r6/06-findings-standing-and-pattern-pass.md:160–176`; the corresponding amendment-ledger row is
`amendment-ledger.md:49`.

**What remains.** No author/auditor independent execution is claimed. A later independent execution
may be produced as new evidence, but this remediation neither performs nor anticipates it. Whether
the Stage-4 condition lifts is reserved to the fresh delta verifier.

### IR6-A02 — 19/19 predecessor disposition

**Stage-4 defect.** The pre-repair baseline has 19 uniquely numbered findings. The successor accounted
for 17; `INT-R6-F002` and `INT-R6-F014` had zero individual dispositions.

**Remediation.** A complete exact-file heading read at `b612b21272c732d53cfde8569846cfb7a0c73f5a`
counts `INT-R6-F001`–`INT-R6-F019`: **19 unique IDs**. Two rows are added:

| ID | original method | original denominator | disposition |
|---|---|---|---|
| `INT-R6-F002` | compare the named Wave-2 `INT-R6` backlog row with governing D4-A1 | 1 named backlog row + 1 governing D4-A1 record | restored as historical framing with the D4-A1 supersession boundary |
| `INT-R6-F014` | complete read of `apps/runtime-dashboard/src/api/validators.ts` outside the closed decision-validity member set | 1 named validator file; declarations outside the named closed set | restored as a bounded open-string observation; adoption remains owner-by-owner |

The successor count is now:

```text
numbered predecessor findings 19
individually dispositioned 19
unaccounted 0
```

**Carrying location.** `int-r6/01-repository-baseline.md:114–181`; the corresponding amendment-ledger
row is `amendment-ledger.md:47`.

**What remains.** The three non-duplicative delivery/orientation claims from the removed 139-line
main file remain unchanged and separately accounted. No new research claim was needed to record
F002 or F014.

### IR6-A05 — complete owner-state split

**Stage-4 defect.** Twenty-five F-rows carried explicit `unallocated`, three owner-only rows named
governing identities, and F-010/F-027 named the `INT-R6 research package`, an artifact rather than an
accountable identity: 28/30.

**Remediation.** F-010 and F-027 now state explicit `unallocated`; no owner is invented and neither is
routed to a generic work lane. The complete 30-row census is:

```text
rows with explicit unallocated state 27
rows with existing-owner identity only 3
rows naming an artifact as owner 0
rows naming a generic work lane as owner 0
total 30
```

The 27-row category includes mixed rows that also name bounded existing component owners. The three
owner-only rows are F-001, F-009, and F-023.

**Carrying location.** `int-r6/06-findings-standing-and-pattern-pass.md:14–58,160–175`; the
corresponding amendment-ledger row is `amendment-ledger.md:50`.

**What remains.** F-010 and F-027 remain unallocated until a competent later process binds an owner.
This remediation does not appoint one.

## Bounded substantive delta

The substantive endpoint is the content commit named in the receipt section. Before hashes are from
the exact verification head. After hashes are the content-commit blobs; the receipt-only successor
changes only this ledger to record the immutable content-commit receipt.

| touched path | before blob at verification head | after blob at content commit | semantic scope |
|---|---|---|---|
| `policy-engine/docs/research/policy-operations/int-r6-multilingual-authority-equivalence-protocol.md` | `e43cef7fef428cabf9a836d48e1127aaa433bc05` | `5547abc89afb00cf594540e1bc1068b613faff92` | A04 Terminal B in the substantive report |
| `policy-engine/docs/research/policy-operations/int-r6/01-repository-baseline.md` | `08a69f3194b46a51f6a8b31daa70e2f34c046d08` | `2ab6d88f3eb78d7c363a1aad6b82b95b5fb6dc1e` | A04 Terminal B; A02 F002/F014 disposition |
| `policy-engine/docs/research/policy-operations/int-r6/06-findings-standing-and-pattern-pass.md` | `28c277d7e35e23a995bf17bdbfce7d1c546687e2` | `2cb380e50c3239b503344fe986fa7c4a665e1e4f` | A05 owner states; A04 evidence label |
| `policy-engine/docs/research/policy-operations/int-r6/amendment-ledger.md` | `b43a0435a83f55b5250141620011d6aa7d9a4b20` | `3e15e5ac6c2a385a49ebb51d81f9ad2e58c5654e` | only the A02/A04/A05 disposition rows |
| `policy-engine/docs/research/policy-operations/int-r6/remediation-ledger.md` | `absent` | recorded by the receipt-only successor | this bounded ledger and connector receipts |

No source, workflow, staging, binary, `AGENTS.md`, pattern-register, audit, or Stage-4 verification
path is in the delta.

## Connector receipts

### Pre-write ancestry

| base compared directly with verification head | merge base | ahead | behind |
|---|---|---:|---:|
| verification `1accee35…` | `1accee35…` | 0 | 0 |
| amendment `8137aa31…` | `8137aa31…` | 7 | 0 |
| audit `bae4f8c2…` | `bae4f8c2…` | 17 | 0 |
| base `dc7bdf79…` | `dc7bdf79…` | 49 | 0 |

Every `merge_base_commit.sha` equalled the stated base and every `behind_by` was `0`. Branch
`research/int-r6-remediation` was absent before creation and was created from exactly
`1accee3534befa8ce9bc656a1b35f8eaca7e9b74`.

### Tree-read discipline

- The full-root recursive read at verification tree `d339fe53b89f710fd255fb635bb09234f8b85918`
  was connector-response-clamped before GitHub's own `truncated` field was observable. It was
  discarded and supports no count, zero, or positive.
- Verification-head `int-r6` recursive subtree `769a35fe09921963b6496adc20ac32e19ae43191` reported `truncated:false` and exactly seven Markdown blobs.
- All other tree reads used to traverse to that subtree were non-recursive; no `truncated` claim is attached to them.
- No code-search result settles a zero, positive, count, or distribution in this remediation.

### Two-commit convention

```text
content_commit_sha: recorded by the receipt-only successor
receipt_only_successor_parent: same content commit
```

The content commit carries every substantive change. This receipt-only successor changes only this
ledger to record the content-commit SHA, content-head blob set, tree-read results, and final ancestry
observations. A commit cannot embed its own SHA; the final branch-head SHA is therefore reported in
the delivery hand-back and remains directly readable from the branch ref.

The receipt-only successor appends the immutable content-commit SHA, the content-head blob set, the content-subtree `truncated` result, and the exact content delta. The final successor SHA is reported in the delivery hand-back because a commit cannot contain its own SHA.
