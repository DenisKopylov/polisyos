---
title: PAO-R36 Amendment Verification - Orientation Ledger
verification_id: PAO-R36-AMV
status: delivered_independent_verification
verdict: CONFORMS_WITH_GAPS
blocking_findings: 0
material_gaps: 1
verified_amendment_commit: 926326174135ef6e407037ebcbe2094228430729
audited_commit: 1bccc012b636d6a13930735a4f748d1f8cf7b9cf
independent_audit_commit: 9bbfd37a218222ae06c1f669b95dba37c4732765
documentation_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
verification_branch: research/pao-r36-amendment-verification
research_only: true
authoritative_for:
  - pao_r36_amendment_verification_orientation
  - pao_r36_amendment_delta_reconciliation
  - pao_r36_amendment_file_and_blob_register
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, media-type, or API contract
  - canonical owner, vendor, archive, signer, publication-of-record venue, or service appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional conclusion
  - permission to publish or open a gate
  - repair or mutation of the amendment branch
  - automatic amendment of any plan, backlog, audit, or system-design decision
---

# PAO-R36 amendment verification orientation ledger

## 1. Verification boundary

This ledger independently verifies the repository shape and arithmetic of
`research/pao-r36-amendment@926326174135ef6e407037ebcbe2094228430729` against the audited head
`1bccc012b636d6a13930735a4f748d1f8cf7b9cf`. It does not use the amendment summary as evidence.

The documentation reference is
`main@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`. Source files at that pin are represented by the
commission as byte-identical to the original source pin. Internal documentation and ratified-kernel
claims are therefore checked at the documentation pin; amendment text is checked at the reported
amendment commit.

## 2. Branch topology and changed-file scope

The remote comparison independently returns:

- status `ahead`;
- **8 commits ahead** and **0 behind** the audited head;
- merge base exactly `1bccc012b636d6a13930735a4f748d1f8cf7b9cf`;
- **8 changed files**: seven modified and one added; and
- every changed file is Markdown under the PAO-R36 research package.

The exact changed set is:

1. `policy-engine/docs/research/policy-operations/pao-r36-public-correction-and-durable-notice.md`;
2. `policy-engine/docs/research/policy-operations/pao-r36/amendment-ledger.md`;
3. `policy-engine/docs/research/policy-operations/pao-r36/comparative-models-and-hard-cases.md`;
4. `policy-engine/docs/research/policy-operations/pao-r36/external-primary-source-and-transfer-ledger.md`;
5. `policy-engine/docs/research/policy-operations/pao-r36/falsifier-suite.md`;
6. `policy-engine/docs/research/policy-operations/pao-r36/ordered-fanout-and-completeness-contract.md`;
7. `policy-engine/docs/research/policy-operations/pao-r36/orientation-ledger.md`; and
8. `policy-engine/docs/research/policy-operations/pao-r36/repository-integration-and-dependencies.md`.

No changed path is under `policy-engine/src`, `.github/workflows`, an audit branch directory, a
sibling research package, a binary/staging directory, or a transport/automation location. The diff
contains no workflow, source, binary, base64 transport, staging, or self-executing artifact.

## 3. Amended file line counts and blob identities

Each file was read from the exact amendment commit through its reported last line, followed by a
one-line overrun read that returned no additional content.

| File | Independently read line count | Blob SHA at amendment commit |
| --- | ---: | --- |
| `pao-r36-public-correction-and-durable-notice.md` | **509** | `11256bbf283939c89e0aaf885a9d00792a17311f` |
| `pao-r36/ordered-fanout-and-completeness-contract.md` | **480** | `c190a8cca4ef891d08da661a039fbbaf89d98b3b` |
| `pao-r36/falsifier-suite.md` | **698** | `ec84ea3e33a55deae59236d7612dc263fca2e925` |
| `pao-r36/comparative-models-and-hard-cases.md` | **258** | `72b946e5a2c242bd9c3bc0b2bc7d420810851232` |
| `pao-r36/repository-integration-and-dependencies.md` | **180** | `73a29ee4c99e162bd5ef5b27d0b5e1ef1d579442` |
| `pao-r36/orientation-ledger.md` | **190** | `4cc3a444389f7477feb7365ef6c4a539c4b0732a` |
| `pao-r36/external-primary-source-and-transfer-ledger.md` | **82** | `53d4a7ffac164d8b9269a0d93b7d749460607ffd` |
| `pao-r36/amendment-ledger.md` | **167** | `f7e9c6da99f90b3810b8fc9f601a9412d9e22571` |

The amendment line total is independently recomputed as:

`509 + 480 + 698 + 258 + 180 + 190 + 82 + 167 = 2,564`.

## 4. Audited-package line total

The seven audited files were independently read through their exact endpoints at the audited head:

| Audited file | Line count |
| --- | ---: |
| primary report | 684 |
| ordered contract | 538 |
| falsifier suite | 374 |
| comparative models and hard cases | 241 |
| repository integration and dependencies | 216 |
| orientation ledger | 174 |
| external source ledger | 70 |

The audited total is:

`684 + 538 + 374 + 241 + 216 + 174 + 70 = 2,297`.

Therefore the file-total delta, subtracting the audited package from the amendment package, is:

`2,564 - 2,297 = +267` lines.

## 5. Remote diff arithmetic

The same remote comparison independently reports these per-file additions and deletions:

| File | Additions | Deletions |
| --- | ---: | ---: |
| primary report | 472 | 647 |
| amendment ledger | 167 | 0 |
| comparative models and hard cases | 215 | 198 |
| external source ledger | 49 | 37 |
| falsifier suite | 561 | 237 |
| ordered contract | 416 | 474 |
| orientation ledger | 132 | 116 |
| integration and dependencies | 152 | 188 |
| **Total** | **2,164** | **1,897** |

The diff-total delta is:

`2,164 - 1,897 = +267` lines.

Both independent paths reconcile:

`amended file total - audited file total = remote additions - remote deletions = +267`.

This is strong evidence that the amendment's file inventory and arithmetic were prepared carefully;
there is no cross-comparison subtraction error of the kind the commission warned against.

## 6. Census claim and P35 method

The amendment records this complete-walk census:

| Token | Path denominator | File-type denominator | Files | Matching lines | Occurrences |
| --- | --- | --- | ---: | ---: | ---: |
| `supersede` | `policy-engine/src` | all source; all 48 reported Python | 48 | 215 | 260 |
| `superseded` | `policy-engine/src` | all source | 34 | 154 | 183 |
| `retraction` | `policy-engine/src` | all source | 7 | 40 | 45 |
| `retraction` | `policy-engine/src` | Python only | 6 | 39 | 44 |
| `cache_invalidat` | `policy-engine/src` | all source | 3 | 5 | 6 |
| `subscriber` | `policy-engine/src` | all source | 3 | 18 | 21 |
| `correction_notice` | `policy-engine/src` | all source | 0 | 0 | 0 |
| `notify_subscribers` | `policy-engine/src` | all source | 0 | 0 | 0 |
| `correction_feed` | `policy-engine/src` | all source | 0 | 0 | 0 |

The declared matching operation is case-sensitive fixed-string matching over a complete pinned tree,
with binary files excluded. The documentation pin's P35 register independently records the index
rider and the same `supersede` 48/215/260 result, including the mechanism by which the audit's index
candidate set was one file short.

### 6.1 Independent execution limitation

The verification environment exposes exact file reads and Git tree metadata, but it does not expose
a complete exact-ref archive or a recursive tree-plus-blob content walk as one executable operation.
The recursive tree response is too large for complete connector return, code search returns an
indexed/ranked set rather than a P35 denominator, and archive download through ordinary egress is
blocked. Those methods cannot independently establish either a positive count or a zero.

Accordingly:

- the audit's 47/203/246 result is **not admissible as a complete census**, because its starting set
  was an index result and P35 forbids treating that set as a denominator;
- the amendment's explanation of why the audit result is declined is methodologically supported by
  the registered P35 evidence; but
- this verifier did **not independently re-execute** the complete literal census from every source
  blob and therefore cannot certify the replacement 48/215/260 or the other literal counts as a new
  independent tree measurement.

This is finding `PAO-R36-AMV-I-001`, classified **material, non-blocking**. It does not reopen the
three semantic blockers, but it prevents an unqualified `CONFORMS` result for the complete requested
verification scope.

The settling evidence is one fresh exact-ref command or equivalent complete walker that prints, for
each token, the path denominator, file-type denominator, distinct files, matching lines, and
occurrences—for example a working `git grep` over
`109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee` or a recursive Git tree/blob script whose complete output
is retained.

## 7. Orientation disposition

- Branch topology: **conforms**.
- File-type and changed-path scope: **conforms**.
- Per-file line counts: **conform**.
- Both `+267` arithmetic derivations: **conform and reconcile exactly**.
- Complete census execution: **not independently established in this environment**.
- Audit I-001 decline: the audit result is correctly rejected as a P35-complete census; the exact
  replacement count remains the one material independent-verification gap.
