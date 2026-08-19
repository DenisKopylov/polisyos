---
title: "Stage-0 Source Manifest"
status: delivered
kind: research-provenance
research_scope:
  - PAO-R0
  - PAO-R1
  - OPS-R15
repository: "https://github.com/DenisKopylov/polisyos"
repository_branch: main
repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
consolidation_commit: a55d33c7a2ed160fd609b1a9e07d95e0bbb04e19
amendment_branch: research/stage0-anchor-amendments
manifest_date: 2026-07-29
authoritative_for:
  - identity and SHA-256 of the three user-supplied Stage-0 source artifacts
  - byte identity between supplied artifacts and repository frozen copies
  - provenance chain used for the compressed amendments
may_not_use_for:
  - identity with an unavailable earlier Deep Research export
  - substantive research authority
  - production capability claim
  - authority grant
  - implementation authorization
research_only: true
---

# Stage-0 Source Manifest

## 1. Purpose

This manifest closes the source-artifact limitation recorded by the Stage-0
consolidation. On 2026-07-29, the user supplied all three reports as local
Markdown files and instructed the amendment work to continue. Those supplied
bytes are the source of record for this amendment.

Each artifact was copied without transformation into `stage0/sources/`, hashed
before and after copying, and retained beside the compressed revisions.

## 2. Source-of-record inventory

| Research task | Supplied filename | Frozen repository path | Lines | Bytes | SHA-256 |
|---|---|---|---:|---:|---|
| PAO-R0 | `pao-r0-policy-matter-identity-and-episode-graph.md` | `sources/pao-r0-original.md` | 1,948 | 121,049 | `f7d100465e869dc75165bd6c1b7e7029bcd5ffbe5514a47df1f5343aecd2b840` |
| PAO-R1 | `pao-r1-operational-boundary-decision-register.md` | `sources/pao-r1-original.md` | 2,091 | 145,532 | `ea19d89c5fdfde6b64f1509c3c19a19bdca89149901dde7b82e3ed21276e1355` |
| OPS-R15 | `OPS-R15_PolicyOS_Custody_Cycle_Capstone_Benchmark.md` | `sources/ops-r15-original.md` | 2,672 | 208,289 | `0c3baf41df8ae02bd9f9ae88cc9f1a350d7f4e33021a94327c3e578044690d15` |

The OPS-R15 digest and 2,672-line count match the independent audit's prior
record exactly.

## 3. Byte-identity result

| Source | Supplied SHA-256 | Frozen SHA-256 | Result |
|---|---|---|---|
| PAO-R0 | `f7d100…b840` | `f7d100…b840` | `byte_identical` |
| PAO-R1 | `ea19d8…1355` | `ea19d8…1355` | `byte_identical` |
| OPS-R15 | `0c3baf…0d15` | `0c3baf…0d15` | `byte_identical` |

Verification used SHA-256 over raw file bytes. Newline normalization,
frontmatter rewriting, citation cleanup, and Markdown reflow were not applied
to the frozen copies.

## 4. Formatting and conversion disclosure

| Question | PAO-R0 | PAO-R1 | OPS-R15 |
|---|---|---|---|
| Transformation during amendment ingestion | None | None | None |
| Supplied-to-frozen byte identity | Verified | Verified | Verified |
| Earlier Deep Research export available for comparison | No | No | No |
| Identity with an earlier export claimed | No | No | No |
| Source-of-record basis | User-supplied artifact on 2026-07-29 | User-supplied artifact on 2026-07-29 | User-supplied artifact on 2026-07-29 plus matching audit digest |

PAO-R0 and PAO-R1 were assembled as files before this turn from report text
previously supplied in chat. Their formatting history before the files were
attached is not independently observable. This manifest therefore proves
identity with the attached source-of-record bytes, not with an unavailable
earlier export.

The OPS-R15 frozen source includes conversation-specific citation-marker bytes.
They remain unchanged for provenance. The revised report does not reuse those
markers as citations.

## 5. Research and audit lineage

| Stage | PAO-R0 | PAO-R1 | OPS-R15 |
|---|---|---|---|
| Historical repository baseline | `4813b49f6ce14e8debf3aaea096f0967d38d9768` | Same | Same |
| Independent audit commit | `258aa740efcfb9e6771bfe52d4fdabc6b74f93a7` | `566840c330e867a15313923c87c20b6863cb053f` | `42a79a655974b37e28a89d31b5f72ffea83927f4` |
| Cross-audit synthesis | `a55d33c7a2ed160fd609b1a9e07d95e0bbb04e19` | Same | Same |
| Amendment branch point | `a55d33c7a2ed160fd609b1a9e07d95e0bbb04e19` | Same | Same |
| Revised result | `research_supported_with_open_owner` | `accepted_narrower_scope` | `blocked_pending_oracle_independence` |

The historical and current `main` commit were both
`4813b49f6ce14e8debf3aaea096f0967d38d9768` when the audits and synthesis were
pinned. The amendment is stacked on the exact consolidation head rather than
silently recomputing findings from a different baseline.

## 6. Audit artifacts used

The amendments rely on the exact audit commits above and the nine-file
consolidation package in
[`../consolidation/stage0/`](../consolidation/stage0/). The consolidation
recorded these source audit hashes:

### PAO-R0 audit

| Audit artifact | SHA-256 |
|---|---|
| `pao-r0-independent-audit.md` | `231656dcef46efca64fdf1d18a79e44201bb77744850f74638aafaf630966557` |
| `pao-r0-claim-evidence-ledger.md` | `9d395157bf7eab96b1a6f67f93ab1ca07d3180c0c4fad1ca3f4aac4e9a052b26` |
| `pao-r0-recommended-revision.md` | `e76af0bfeeef43bda72f2d6f1291c892dbb096be7f8e14b84ff08a9b230c6390` |
| `pao-r0-test-and-fixture-verification.md` | `a270341adb50ebc3b4774c10af28d95c2fde8d7500a7aa4d7597bc0aff008c67` |

### PAO-R1 audit

| Audit artifact | SHA-256 |
|---|---|
| `pao-r1-independent-audit.md` | `2ae1b38d8d764bb0bc130e3bdf82304b4e8ee4b596697a7c8af4d63f3bcc15af` |
| `pao-r1-register-row-audit-ledger.md` | `7be50648b1324958910125a48515d72c3c804b31cbafad31d2fa8456c7f8b708` |
| `pao-r1-evidence-contract-audit.md` | `1b924647d7a0d1088213da3cf6807fdfeaaf6d9236c5c31d8cd7f17518fdd4a2` |
| `pao-r1-contradiction-and-consistency-ledger.md` | `1e5e29ca2511c00e04ca7c875818b2f62f3e2114daea7925eb4641aee660a0c0` |
| `pao-r1-recommended-revision.md` | `a5a0806ff857211fd1a7f097dfb2660b7abd3e6cc676fe1e6286709b89dcf5a0` |
| `pao-r1-test-and-fixture-verification.md` | `63bd34b93502a677c940e798fe85d53042795ed56055d3f4a9e0bb6b50418aff` |

### OPS-R15 audit

| Audit artifact | SHA-256 |
|---|---|
| `ops-r15-independent-audit.md` | `7abd085262468ba973ca612edda6def06e613fc9c97edf9657949b13c0777aff` |
| `ops-r15-calendar-event-audit-ledger.md` | `18b5bbdc1ae51219a5e29a984226c060f06199d5faa0e6337409812d511f9929` |
| `ops-r15-metric-and-oracle-audit.md` | `bd4a16cee95f2765de9d9cbc3945ab010aeac4fa3935d0be77ea8b636632194b` |
| `ops-r15-state-contract-and-owner-audit.md` | `6785b69e76bad1206810da608de6bd3fb855cf60f7b783b10be24698a776153e` |
| `ops-r15-stage0-kernel-and-extension-packs.md` | `e12c301d11b1635268bc20e5d05bb5bb84c50373545f348c2befa731a7ae0f3a` |
| `ops-r15-recommended-revision.md` | `0d18449bdfd57a145f644546fc213d63cd036531e82bfeabe999fc2f0ae3fa75` |
| `ops-r15-test-and-probe-verification.md` | `d25f2286ff462756938513cda5873a77a8d19e2043cffa2dbc1dac09c37c0bcf` |

These hashes identify the audit evidence used by the synthesis; the audit files
are not duplicated into this directory.

## 7. Output inventory

| Role | Repository path | Initial line count after amendment |
|---|---|---:|
| Revised PAO-R0 | `pao-r0-policy-matter-identity-and-episode-graph.md` | 506 |
| Revised PAO-R1 | `pao-r1-operational-boundary-method-and-evidence-interface-census.md` | 570 |
| Revised OPS-R15 | `ops-r15-custody-capstone-semantic-kernel-and-benchmark-architecture.md` | 594 |
| Source manifest | `stage0-source-manifest.md` | This file |
| Amendment ledger | `stage0-amendment-disposition-ledger.md` | Generated in the same change |
| Conformance report | `stage0-amendment-conformance-report.md` | Generated in the same change |
| Frozen PAO-R0 | `sources/pao-r0-original.md` | 1,948 |
| Frozen PAO-R1 | `sources/pao-r1-original.md` | 2,091 |
| Frozen OPS-R15 | `sources/ops-r15-original.md` | 2,672 |

Line counts are descriptive, not identity. SHA-256 controls the frozen source
identity.

## 8. Transformation policy

The transformation deliberately differs by artifact class:

| Artifact class | Policy |
|---|---|
| Frozen sources | Exact copy; no edits, reflow, citation cleanup, or frontmatter changes |
| Revised reports | Semantic rewrite and compression under the audit/consolidation dispositions |
| Disposition ledger | Maps every required amendment and original section family to its result |
| Conformance report | Records fresh mechanical and repository checks plus declared blockers |

Material removed from the revised reports is not destroyed: it remains in the
frozen source. Removal from an accepted conclusion means “historical research
only,” not deletion of evidence.

## 9. Integrity verification procedure

The source gate is:

```text
SHA256(supplied PAO-R0) = SHA256(frozen PAO-R0)
SHA256(supplied PAO-R1) = SHA256(frozen PAO-R1)
SHA256(supplied OPS-R15) = SHA256(frozen OPS-R15)
```

The conformance report records the fresh command result used before commit and
publication. Any later source edit changes the digest and fails the gate.

## 10. Limitations

- The source-of-record designation is user-provided; no independent earlier
  export was available for R0/R1 comparison.
- A cryptographic digest proves byte identity, not factual correctness.
- The audit and synthesis documents remain research-only and do not grant the
  revised reports production authority.
- External institutional facts and benchmark oracle independence cannot be
  established by source preservation.
