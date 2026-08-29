---
title: "INT-R5 — Amendment verification orientation ledger"
amendment_head_verified: 70f2db6d3a4330664c981721a9305f16bffe369b
orientation_result: architect_baseline_agrees
stage3_handback_accuracy: inaccurate
---

# INT-R5 Amendment Verification Orientation Ledger

## 1. Scope

This ledger separates supplied orientation, connector measurement and correction. Repository
measurements are GitHub connector observations pinned to amendment SHA
`70f2db6d3a4330664c981721a9305f16bffe369b`. No SHA was inferred or reconstructed.

## 2. G1–G7 remeasurement

| Ground truth | Supplied value | Verifier measurement | Result |
|---|---|---|---|
| `G1` containment | audit→amendment `7`; package→amendment `22`; base→amendment `29`; all `behind_by=0`; exact merge bases | GitHub `compare_commits` returned exactly those three counts, zero behind, and each named base as merge base. Amendment→new branch was initially identical. | **agree** |
| `G2` delta shape | 7 paths: 5 modified, 2 added; 0 non-Markdown; 0 audit files | Audit→amendment compare returned five modified package Markdown files plus `amendment-ledger.md` and `survey-source-manifest.md`; no audit path changed. | **agree** |
| `G3` edit volume | main 1,222; specification 724; external 535; fixtures 533; baseline 505 | Compare returned the same changed-line counts. | **agree** |
| `G4` dispositions | 18 unique rows; `16/2/0`; variations A-003/A-005; severities `0/7/2/9` | Row-by-row ledger read returned the same IDs, labels and counts. | **agree** |
| `G5` vocabulary | every disposition is in pipeline §3.3 closed set | All rows use only `accepted`, `accepted_with_variation`, `declined_with_reason`. | **agree** |
| `G6` spot corrections | main inequality `1→0`; bare stale/revalidate tokens `2→0`; PAO-R4 in spec `2→8`; cure terms in spec `1→6` | Complete old/new file reads returned the same counts. The remaining “theorem” says “not a theorem” and is not a surviving theorem claim. | **agree** |
| `G7` standings | `accepted_narrow_scope` / `absent/unallocated` / `NO_GO` unchanged | Every package file carrying an axis retains those exact values; no axis moved. | **agree** |

## 3. Stage-3 hand-back divergences

| Subject | Stage-3 hand-back | Branch measurement | Disposition |
|---|---|---|---|
| Changed paths | “exactly six”; no separate manifest | **seven** paths, including 173-line `survey-source-manifest.md` added in commit `697114234bb6592a2a40aa6725af0f31d1ce90b3` | Hand-back inaccurate; branch graded. |
| Dispositions | `17 accepted / 1 variation / 0 declined`; A-005 only | **16 / 2 / 0**; A-003 and A-005 are variations | Hand-back inaccurate; arithmetic alone would not detect it. |
| Candidate reason namespace | `candidate.polisyos.int_r5.<slug>@0.1.0` | `polisyos.int_r5.reason.<slug>@0.1.0-candidate` | Hand-back inaccurate. |
| Acquisition placeholder name in Stage-4 orientation | `AcquisitionDecisionAuthorityBridge` | No such CamelCase identifier. Package names lowercase `acquisition_authority_bridge` and marks it a research placement, not an implemented owner. | Orientation naming corrected; no package defect. |

The branch delivered more work than the hand-back described. `disclosure_accuracy` is therefore
**inaccurate**, while `delivery_and_containment` remains **conforming**.

## 4. Connector receipt ledger

### 4.1 Exact source pin and initial branch state

- GitHub ref read:
  `research/int-r5-amendment` →
  `70f2db6d3a4330664c981721a9305f16bffe369b`.
- Verification branch created at exactly that SHA.
- Initial amendment→verification compare: `status=identical`, `ahead_by=0`, `behind_by=0`,
  merge base `70f2db6d3a4330664c981721a9305f16bffe369b`.
- Initial audit→verification compare: `ahead_by=7`, `behind_by=0`, merge base
  `247f89f016f71ee603ed76ef6dbb6403f7e651a0`.
- Initial package→verification compare: `ahead_by=22`, `behind_by=0`, merge base
  `02e203de90d51280d569e7f641a158569ae4df39`.
- Initial base→verification compare: `ahead_by=29`, `behind_by=0`, merge base
  `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`.

For each compare, exact merge base plus `behind_by=0` is exactly the ancestor predicate.

### 4.2 Headings-only delivery

| Artifact | Skeleton commit |
|---|---|
| `int-r5-amendment-conformance-verification.md` | `d1b7e0691caa046ac069641193a7b291ef8fae6c` |
| `int-r5-commendation-and-manifest-ledger.md` | `4897a7039d68febbf2ba84b7a067375acab7eaef` |
| `int-r5-amendment-verification-orientation-ledger.md` | `d3ff912e7c6f55e06ddb3ba728bc620efcb496a4` |

### 4.3 Tree and denominator observations

- The GitHub recursive-tree response was connector-clamped before the response field
  `"truncated"` could be observed. It was not used for a set-level claim.
- A pinned GitHub Contents walk enumerated `services/control/` as 15 Python files with no child
  directory. Each exact raw file was fetched; full-response text scans found
  `HumanDecisionService` in `0/15`.
- Final delta and final containment are established by post-write `compare_commits`, not inferred from
  the recursive tree.

## 5. Orientation errors made and corrected

During verification, an early Library title search surfaced duplicate deep-research objects with
different `file_…` identities. That did not disprove the manifest. The verifier corrected course by
reading and materializing the **exact identities recorded in the manifest**; all five resolved and
their byte/hash denominators matched. The duplicate-title results were not used as evidence against
A-005.

The remaining A-005 gap is narrower: branch-only third-party retrieval and complete passage coverage,
not authenticity of the recorded hashes.
