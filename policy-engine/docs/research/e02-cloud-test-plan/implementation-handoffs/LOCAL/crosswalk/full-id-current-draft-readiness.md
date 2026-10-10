# Full-ID current-draft readiness

**Status:** occurrence crosswalk preparation only. This is not a v4 evaluation input, source freeze, test receipt, candidate disposition, or G decision.

The full, machine-readable preparation join is retained locally at [`raw/full-id-closeout-preparation/full-id-current-draft.json`](../raw/full-id-closeout-preparation/full-id-current-draft.json) (`path@SHA-256`: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/full-id-closeout-preparation/full-id-current-draft.json@b04812ae40f423c6c5105a9ffa781a0c8830d05c14ad9f5cdfabb2d5fad3f894`, 2,267,749 bytes). It was moved without content change from the crosswalk directory; byte-for-byte and SHA-256 readback matched. The path is ignored by the existing `policy-engine/.gitignore` raw-directory rule. This tracked note retains the decision-useful denominator and source-packet bindings without committing the large derived inventory.

## Source bindings

The join used the following authoritative inputs and owner packets. All 17 file hashes were read back against the draft’s source-packet registry; JSON pointers in the normalized report resolve to the cited files.

| Role | Path | SHA-256 |
|---|---|---|
| Original coverage denominator | `policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/coverage.json` | `97860dc18c7b92124971aa8032fc229be3367723ea2ec45e6cda4a777e544e01` |
| Task routes | `policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/unified-local-2026-10-09/TASKS.json` | `a37c75cfe09d33c1f50379d5bbfd04bdb728c990e832aec3bf19c0d17035734c` |
| Existing occurrence ledger | `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/finding-proposals.json` | `1bd47384a114951b89305ec48892593ae061933d9d0b2fa884e63a47b3b97908` |
| Final-input contract | `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/decisions/full-id-closeout-report-input-contract.md` | `5cb4a326624fdd86e1c366fabd71fae6f7c0ca4bece1dc5627a7d78907cb8ee6` |
| A assessment / current-source audit | `LOCAL/reviews/full-id-A-assessment.json` / `LOCAL/reviews/full-id-A-current-source-delta.md` | `4013536c5087c3cb3c90f2563b695f3e57455719efe87c42c85c979f92a649ab` / `4b6db8c7cbc371b83def47662872c3fcd62a35067caef09eef06b042a28318fe` |
| B assessment / current-source audit | `LOCAL/reviews/full-id-B-assessment.json` / `LOCAL/reviews/full-id-B-current-source-delta.json` | `07c722aae037f0c3ab94c3d2350178309a2008bf73a65605e6a3de40e63007b8` / `ba853c6169910b990e681915fcb5860b89b31365d15d88aa34a2199a1b4311bf` |
| C assessment / current-source audit | `LOCAL/reviews/full-id-C-assessment.json` / `LOCAL/reviews/full-id-C-current-source-delta.json` | `72c50f92c75f12ebc89de1c1eff01a1925f1e3e89f3b7ff0e7b8561cad419972` / `e6e72a7efc5c3d7b9d3e27ff3ca264336f5307885c0607946b13c965fa9293c5` |
| D assessment / current-source audit | `LOCAL/reviews/full-id-D-assessment.json` / `LOCAL/reviews/full-id-D-current-source-delta.json` | `67eb68112863ec176f8b245391710d0ef13c656eb88fc6fca876e744b3c6fdc0` / `e066b3cd2da8ab8cd969a5c7f931061865d263a581dc12d441265fa4f62e4e06` |
| E assessment / current-source audit | `LOCAL/reviews/full-id-E-assessment.json` / `LOCAL/reviews/full-id-E-current-source-delta.json` | `4746552f09ca00cd2705c94e1ff3e7dff2ad6c8576c228839221e51eacee65cf` / `ca4c2050fd77cf6a1c2f4d7081ed9e5607df11d140a0ce723efd92eb727d122b` |
| F assessment / current-source audit | `LOCAL/reviews/full-id-F-assessment.json` / `LOCAL/reviews/full-id-F-current-source-delta.json` | `c3ea21de3bb9949ceffd8cb22d1790368e9fb3c68ed687b2483abd5b94c675bc` / `bd4c81a2652fafe80bcc4aa9adea661cbbd83043ea6ab0ec04e82a06051c05fc` |
| D45 action source referenced by D | `policy-engine/docs/research/e02-cloud-test-plan/integration/reviews/2026-10-07-CD-C4-a795/D45-decisions.json` | `b1187770c7279a4fa72abd92d018ff8e562e795be7596a733e911136c9325256` |


## Reconciliation and validation

The draft joins the complete original occurrence multiset on the exact pair `(coverage occurrence pointer, original span SHA-256)`. It preserves duplicate occurrences as separate rows, links each row to the corresponding A–F assessment and current-source audit locator, and records each task-route pointer as routing context only.

| Owner packet | IDs | Occurrences |
|---|---:|---:|
| A | 34 | 35 |
| B | 60 | 60 |
| C | 54 | 59 |
| D | 45 | 46 |
| E | 54 | 55 |
| F | 35 | 36 |
| **Total** | **282** | **291** |

Complete-walk checks also confirmed 127 bundles; 26 task definitions and 319 ID-route assignments; Q0 scope of 206 IDs / 212 occurrences; 190 occurrences with `owner_property_boundary_state=not_established_by_author_crosswalk`; and 55 with `acceptance_boundary_state=original_source_span_only`. Source-author proposal counts are 198 `closed`, 54 `limited`, 23 `held`, and 7 `open`; all 198 `closed` proposals are routed in Q0. These are source and route counts, not current candidate outcomes.

Lightweight validation passed: the output’s 291 exact keys match the canonical ledger multiset; all 17 registered packet hashes match current readback; all normalized JSON pointers resolve; and all evaluation rows have `state=UNRUN`, null candidate source/result/disposition, empty attempts/evidence, and no formal closures. The current action summary repeats one broad rebind/replay instruction across E’s 55 rows, so the draft retains distinct row-specific source-family, consumer-chain, selector, criterion, and P40 pointers. None of these planned checks is represented as executed.

## Preserved history and limits

B198 remains historical ledger `closed`, Appendix C `closed_bounded`, and `closure_now=not_adjudicated`, with source-author proposal `closed`; its current occurrence evaluation is `UNRUN`. The report carries `formal_closure_ids: []`.

The preparation checkpoint recorded in the raw draft is HEAD `c9d0941864a801e3f143b5cc2e94ec1c26f72e22`, tree `f5ba738afdd7b65bf9d244a595747c18910eb3ea`. This is navigation context, not the final source/configuration/input/backend/profile freeze. No current final-wave command attempts or independent frozen-candidate review are bound. The draft cannot support `VERIFIED`, `BOUNDED_LIMITATION`, `UNAVAILABLE_INPUT`, or `OPEN_ACTION` dispositions; root must join actual occurrence-specific evidence under the v4 contract after the final freeze. Task PASS, prior-candidate receipts, historical status, and source-author proposals do not fill that gap.
