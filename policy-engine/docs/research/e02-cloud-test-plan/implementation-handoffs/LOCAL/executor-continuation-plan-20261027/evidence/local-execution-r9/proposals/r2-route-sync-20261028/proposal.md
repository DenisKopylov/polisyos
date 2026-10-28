# R2 provenance route-sync proposal (unapplied)

## Scope

This is an R2-only author documentation proposal. It changes four route-summary surfaces in memory and supplies a patch for root review; it has not been applied to tracked files. No product source, tests, G dispositions, review-plan inputs, canonical task bindings, index/ref, or finding status are changed. It adds no G acceptance or closure.

The `QUEUE.json` top-level `base_commit`/`base_tree` and row `current_source` are preserved as the continuation plan's historical entry identity. The existing `analysis/review-plan.md` input manifest also remains untouched; applying any route delta creates a new review input identity that needs the normal root-led document review/rebind.

## Exact proposed footprint

- `executor-continuation-plan-20261027/QUEUE.json#/rows/10`: sync the R2 execution summary with the already-corrected packet, preserve candidate-source qualification, and keep G adjudication separate.
- `executor-continuation-plan-20261027/analysis/runtime-routes.md` R2 block: record the packet correction, actual ancestry, candidate-pinned path boundary, and later current-source delta.
- `executor-continuation-plan-20261027/analysis/criteria.md` B87/B89 row: remove the stale instruction to correct already-corrected roles and preserve the G boundary.
- `executor-continuation-plan-20261027/analysis/dependencies.md` R2-to-I3 row: replace the stale remaining-provenance wording while keeping the same dependency edge.

Exact before/after text is in `proposal.patch`. The queue JSON change uses exact string surgery; no full-document JSON reserialization is proposed.

## Canonical bindings and authority

- Original task: `policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/unified-local-2026-10-09/TASKS.json#/tasks/R2`, findings `B87` and `B89`.
- Handover binding: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/executor-handover-20261027/canonical-task-bindings.json#/rows/10`.
- Route binding: `analysis/criterion-routes.json#/canonical_routes/R2`; occurrences are `B87@NET-01` at `#/occurrences/212` (`B_r19`, `#/findings/212/criterion_refs/0`) and `B89@NET-01` at `#/occurrences/214` (`B_r19`, `#/findings/214/criterion_refs/0`). Both route to R2 and G item `G27-06`.
- G disposition: `g-review-followup-20261027/dispositions.json#/items/5` (`G27-06`; SHA-256 `0e1337a4d5e038dbc7ea13fb82a0913f85f8bb50b34bc7fa4aad2f1c54c4082f`). It records `properties_satisfied_provenance_correction_remaining`, reports B87/B89 satisfied at candidate `65ac853`, and retains `closure_ids=[]`.
- G review receipt: `g-review-followup-20261027/verification.json` (`kind`: planning metadata and independent review, not a runtime/native gate; SHA-256 `d2deee8d8343af050759009bbc1a1c18ce08e9ef2c00a809806fd3f5438bef18`). It reports a GO for publication on the declared source entry, with `code_acceptance=false`, `closure_ids=[]`, and `global_freeze=false`.

## Provenance checks at frozen snapshot

The four packet entries already carry the corrected related-history role in author commit `1810a18581630afc079aef2747273447cb6f811f` (parent `8db01b1076e425b7998b05a658776c991b7bd594`). Candidate `65ac853e2735e827e27688a6175f1a385901e20e` has slice base `76691bd25ba10bee2caed9826e54cd9d40324ca5` as its parent, one commit after that base. Each of the four cited historical commits exists in the local object database and is not an ancestor of either the candidate or the slice base. The packet's five shared-mechanism SHA-256 pins all match blobs at candidate `65ac853`.

At frozen route-update snapshot `a8bee9746d0ea6c9582648b60944f8a4a27eb31e` (tree `f54638ce89e0c2589d9be3b47809af12bd509c93`), only two of those five pinned Python source paths match the candidate. The three later-byte paths are `event_stream.py`, `streaming.py`, and `cursor_store.py`. Root's normal commits `8ac5cd32…`, `026f0c89…`, and `a8bee9746d0ea6c9582648b60944f8a4a27eb31e` leave all five R2 source-path Git blobs unchanged relative to `8ac5cd32…`; this was read back by path blob identity. This is a current-source affected-delta qualification boundary; it does not rewrite or revoke the historical candidate-qualified G27-06 finding, and it is not a new G acceptance.

## Complete-set provenance-key census

A full-ID Git grep walked all 2,672 tracked Git blobs under `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL` at `a8bee9746d0ea6c9582648b60944f8a4a27eb31e` (path denominator: that complete `LOCAL` subtree; file-type denominator: every tracked blob, including JSON, Markdown, and other text). Each of the four full commit IDs occurs on exactly two tracked lines: its R2 packet binding and the prior `L01-receipt.json` snapshot. The prior receipt is a historical execution record and remains unchanged. No other full-ID binding is present in that subtree.

The four author-route summary surfaces above are the only proposed sync points. Frozen G/transfer records remain unchanged, including the G27-06 disposition, G-review README, independent review file, and handover `remaining-work.md`, `decisions-and-pitfalls.md`, and `subagent-results.md`; they record the state at their own source cut. The L01 receipt is likewise preserved.

## Pattern pass and checks

- `P30`: no module/symbol naming change; the correction is confined to provenance descriptions and their route summaries.
- `P35`: commit ancestry and path-pin claims are derived from complete enumeration of the four bound commit refs and all five packet path pins; the binding-key census includes the full tracked `LOCAL` subtree and states both denominators.
- `P36`: findings are cited by IDs and exact route pointers; all four full binding keys were grepped through the complete tracked subtree, not just the narrative paragraph.
- The four proposed JSON fields parse from the in-memory postimage; `git apply --check` validates the unapplied patch. No product imports or tests were run.

The first command log in this directory retains the earlier read at `026f0c89…`. `final-readback.txt` records this frozen final snapshot at `a8bee9746d0ea6c9582648b60944f8a4a27eb31e`; each file states the immutable source identity it used.
