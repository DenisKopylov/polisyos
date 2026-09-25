# Independent residual-ledger audit

## Verdict

**NO-GO for the current per-finding closure claim.** The full row, source-anchor, mapping, status, owner, and crosswalk census is internally complete. However, 71 findings are marked `closed` on E02 package receipts without a row-level selector-to-card-discriminator link in the ledger evidence. The source inspection probe explicitly leaves their behavioral verdict `UNRUN`; this audit does not infer that the findings fail, only that the cited evidence does not establish their closure at finding level.

Audited ledger branch `codex/e02-r2-ledger` at `df2760d28c744c97dd4eeadeebc1989453a1d00f`. Inputs: `residual_ledger.json@git-blob:d82d0bd95e62ffd3e3d1e22228c7863e72b89a40`, `RESIDUAL_LEDGER.md@git-blob:cc6c72227335dfff435c3cef76e2cc1d27cc1340`, `finding_record_probe.json@git-blob:cbd03d45bf07b6d35eb99b0b37754a9807a7c397`, `CROSSWALK.md@git-blob:eb914261a19565a25082410626fd5637da8fb4c9`, and `REGISTER_PROPOSALS.md@git-blob:f2d8cdfff1d9839303e5ac298cf957b204e2aaab`. Original cards and maps are `source/B_r19_original.md@git-blob:d800082eebfc12eaf647b0c0257c4f06e135d25a`, `source/LA_r09_original.md@git-blob:4bdf76e99f0c26e40bc2a71e76d4940c23712260`, `finding_to_bundle.json@git-blob:a6d76fefcca9519962e50684d4377d4eec2aa12c`, and `legacy_to_bundles.json@git-blob:329f101acca8dac6708b4e557cd07fd58f5facb7`.

## Complete-denominator checks

A read-only census walked the complete card headings and all ledger rows: **282 source cards (225 B + 57 LA), 282 ledger rows, and 282 unique IDs**. Every row's `source_line` and `source_title` matched its original card; all 282 bundle/owner mappings matched the two mapping files; all required row fields, residuals, comparison details, and typed residual owners were present. No source-only, ledger-only, mapping, or required-field discrepancy was found.

The row data sums to **72 closed, 192 partial, 14 held, and 4 open**. Appendix C status sums to **132 closed_bounded, 118 partial, 14 held, and 18 no_finding_level_record**. P triage is **76 engineering, 16 principal decision, and 26 typed blockers**; the 26 blocker kinds are 11 external institutions, 7 data records, and 8 owner appointments, and each matches its residual-owner kind. Residual-owner kinds across all rows are 89 implementation owners, 133 verification owners, 4 owner decisions, 16 external institutions, 16 data records, 16 principal decisions, and 8 owner appointments.

The crosswalk matrix has **282 unique finding rows**, reproduces all **291** declared finding/bundle memberships, and admits the stated **33 exact owner-scope edges across 27 findings**. No register-row closure is proposed. The five rows whose relation explicitly disagrees with Appendix C—B13, B30, B37, B223, and LA-046—state a source-card-specific reason and retain a status appropriate to their residual. In particular, B29 is closed with no R2 class; B30 is partial and assigned R2, matching the deployment-reuse/currentness discriminator.

Across the ledger JSON and its three companion Markdown files, the complete citation scan found **140 distinct path/digest pairs**: all 131 Git blob IDs exist, all 7 currently resolvable SHA-256 files match, and there are no digest mismatches. Two SHA-256 paths are absent at the cited current-worktree path. The LA-021 checker exists with the stated digest in historical commit `0b71f037cd83785c0b62244dad861dcaaf8c21ed`; cite that immutable revision/blob or a Git blob ID. The LA-021 output exists at `/Users/deniskopylov/.codex/scratch/e02-r2-baselines/la021-canonicalization-20260924.log` with the cited digest, but `REGISTER_PROPOSALS.md` cites only the bare basename, so a reader cannot resolve the path from the repository. Give the full path in the proposal.

## Required corrections

### 1. Provide per-finding evidence for 71 E02-derived closures

The 72 current `closed` rows comprise 71 E02 bounded receipts and the separate LA-021 bounded review. In `finding_record_probe.json`, all 282 row probes are `UNRUN`; among the 72 closed rows, 66 have no package selector group, while B60, B62, B110, B114, B115, and B220 cite only a bundle-level selector group. The probe states that package selectors are not finding-level proof and that no behavioral closure is inferred. The 71 E02 rows cite a bundle J receipt and source bundle, then say that the finding ID is explicitly named in the package record. They do not identify which passed selector exercises that ID's distinguishing property. For example, the CYC-02 receipt reports J0954/J0955 package runs, while the row probe supplies no B04/B05/B08 selector mapping.

Affected rows: **B04–B08, B10, B24, B29, B32, B39, B45–B46, B48, B51, B55, B60, B62, B77, B83–B84, B96–B105, B110, B114–B115, B146, B148–B152, B154–B155, B157, B160, B162, B165, B176–B179, B186–B193, B198, B204–B206, B215, B220–B222, B224–B225, LA-006, LA-013, LA-030, LA-042** (71 IDs).

For each row, add an inspectable selector/result reference and state how it exercises that card's discriminator. A bundle-level receipt can remain supporting context but cannot stand in for that link. If an item-specific witness cannot be produced from the historical run, downgrade that row to `partial` with the evidence gap as its residual. Keep LA-021 separate: its row cites a bounded independent corpus/vector recheck and explicitly retains the untested historical 418-input selector and caller tests.

This correction follows the ledger's own rule at `RESIDUAL_LEDGER.md` lines 23–25: source cards, package acceptance, and triage alone do not close a finding. It also follows `finding_record_probe.json`'s declared `UNRUN` scope; it does not change any test result or assert a behavioral failure.

### 2. Reconcile stale prose counts in `residual_ledger.json`

The JSON's `measurement_limits` at lines 29–31 contradict its actual rows and the matching Markdown summary:

- Line 29 says 73 of 132 Appendix-C `closed_bounded` rows remain closed and 59 are partial. The rows and `RESIDUAL_LEDGER.md` lines 7 and 37–38 show **71 closed and 61 partial**; the current total of 72 closed adds LA-021.
- Line 30 says the other 16 no-record rows are partial. The 18 actual no-record rows are **LA-021 closed, 13 partial, and 4 open**: B09, B27, B72, and B111. `RESIDUAL_LEDGER.md` line 7 has the correct split.
- Line 31 says P triage is 72 engineering / 16 principal / 30 typed blockers. The row objects, `p_triage_counts`, and `RESIDUAL_LEDGER.md` line 12 agree on **76 / 16 / 26**.

Update those prose fields from the complete row census; preserve the correct structured counts and Markdown values. The 73/59 split and 72/30 split currently fail the stated denominator arithmetic.

### 3. Complete the register proposal closure signals

- `REGISTER_PROPOSALS.md` line 70 reports **28 direct** signature-call expressions, but the independent R10 source census finds **29 total invocation sites**: 28 direct plus the retrieved-callable invocation in `runtime/quality/promotion_safety.py:231–242`. The reviewed map is `R10_SIGNATURE_MAP.md@git-blob:f39245cea3b66b393263dfa2853d31f14bac0d53` (held-review candidate). Line 73's closure signal requires all 28 direct expressions and omits the indirect site. Include the 29th invocation and its owner/test witness; do not relabel the 28 direct-call count.
- `REGISTER_PROPOSALS.md` line 66 gives R11's desired complete consumer property but no executable test identity for the positive-N9 blocked run or preserving control. Add proposed selector identities and label them proposed until implemented and run. A prose closure signal is not a receipt.

### 4. Normalize the Appendix-C relation value

The JSON uses both `disagreement` (B13) and `disagrees` (B30, B37, B223, LA-046) for the same relation. Normalize to one value in the machine-readable vocabulary; preserve each row's existing source-specific explanation. This does not change the five rows' status conclusions.

## Limits of this audit

No pytest, native suite, or production-data job was run. This review does not independently replay the E02 J receipts or inspect every historical JUnit artifact for a selector mapping. That is exactly why the 71 closure rows remain unverified by this audit: if the underlying receipts contain item-specific outcomes, cite those outcomes directly in each row. All current four-base finding-level replay fields remain `UNRUN`; `UNRUN` is not a failure and is not evidence of closure.
