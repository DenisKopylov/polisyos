# Independent R10 / R10.1 documentation and evidence review

**Verdict: GO to compose and commit the declared R10 → R10.1 sparse union.** This review checks proposal delivery and bounded evidence wording; it is not G acceptance, product closure, or a fresh test run.

## Integrity and composition

The R10 manifest SHA-256 is `f6c2d7756291456c9a82595364ffd3315fde4f50c2a190c5c26b13bc9be0d31c`; R10.1 is `1c34876a4422882e2da4ef8ceaaf5e47718532d26f0055878cc3c9f53c7ec46d`. Both match. The overlay expressly depends on R10 and applies after it. All **160 rows / 158 unique targets / 1,881,432 unique bytes** match postimage size and SHA-256; every declared gzip payload decompresses to its exact raw size/hash. Both overlays bind their R10 postimage correctly, and all five declared canonical preimages match. No hash, gzip, origin, override, or preimage discrepancies were found.

The EXECUTION ledger is byte-prefix append-only through R10.1. The JSON history retains all prior fields and records; its changing current-view fields have an explicit source/time scope. The queue qualification is surgical: compared with its declared preimage at `ea3d65682d76a5d66d514e525ad2212e5a85f669`, only top-level `scope` changed. All 26 row objects are identical. The note correctly explains that each row's `current_source` is the historical ad81 route-authoring snapshot and points to `execution-state.json` for current observed cuts and source-qualified runs.

## Evidence and time qualification

- R10 binds the committed source cut `8623b3908bb3317060e84f2db7857a971e8887f7` / tree `2bd8450b2b4b5c283ba7840e13ef06abb2a9beed`, while explicitly separating four C60 generated `.pyi` WIP stubs. R10.1 records the later published source `ea3d65682d76a5d66d514e525ad2212e5a85f669` / tree `7c5412fddc4ef3e56c859b83d237162e0fd260e7`; it does not upgrade earlier runtime evidence to that later source.
- C05 carefully separates a failing helper smoke at published 545c (missing required `source`, `TypeError`) from the successful corrected helper smoke and seven selected native PASS at 8623. The seven-case result has its own finite readset and outputs; full C05/HTTP and removal controls remain UNRUN. The original mutable root-live bytes are explicitly unavailable at their old locator and are not reconstructed from hashes.
- C57 preserves the 183-case wave at 575432 as **176 PASS / 3 FAIL / 4 PostgreSQL SKIP**, and separately records six focused SQLite controls at 7382 as PASS. The later controls do not turn the earlier wave green or establish PostgreSQL, removal, HTTP cancellation, or physical-stop behavior.
- C60 preserves the actual Ruff FAIL on four staged `.pyi` paths (`I001/F403`), source/native limitations, and uncommitted WIP; it does not claim generated-family acceptance. C38's 6-case PASS and scoped MDJSON review are similarly bounded from protected issuance and family freshness.
- C71 is upgraded only to the bounded contextual source review and physical Ruff result at ea3d; full HTE, removal, generated-surface, institutional-authority, and G claims remain outside it. C48's guard ERROR is correctly described as stopping before product execution.
- Cloud outcomes remain bound to their submitted task and reconstructed-diff scope. C82 remains ERROR with cause `not_established`; C84 is a submitted retry with no result claimed. Candidate trees are not represented as final Cloud commits or composed-source passes.
- The text preserves exact denominator **26 / 127 / 282 / 291 / 319**, distinguishes 331 expanded occurrence-to-row relations, preserves B198, and keeps G acceptance false with no closure IDs.

## Composition instruction

Apply only the declared R10/R10.1 sparse postimages and overrides; read the committed branch bytes back against their hashes. Keep the C05 missing mutable-input limitation and all source/backend scopes as recorded. No product tests, imports, index/HEAD/ref changes, or canonical files were changed by this review.
