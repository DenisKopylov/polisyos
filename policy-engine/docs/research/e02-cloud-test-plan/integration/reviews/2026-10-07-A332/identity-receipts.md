# A intake 332ba0b — identity and receipt audit

> This independent review was written before the G native run. Its then-UNRUN runtime status is historical; the current exact-source outcomes are in [native-checks.md](native-checks.md). The original source/criterion limitations remain.

**Result:** the acquired head is immutable and internally consistent, but its latest product change has no exact run receipt or matching committed implementation handoff. Keep that delta separate from the older bounded receipts until A supplies an exact candidate receipt. This is identity/evidence admission, not a complete source-code review or a finding-closure decision.

## Pins and footprint

- G is `2abc17f46a033a7879663486ff9946a95786601f` / tree `375301dd0c86a6168f4f747d8c56d9e0acb9567c`. The exact acquired source ref is `refs/e02-g/A-intake-332ba0b` at `332ba0b91e9a85774d48d101d4af86e3a3baf911` / tree `4e21c90467913c6dae1c85b84b8c7a42a1dc9124`; declared slice base `2605d13916f4dd38f216419562c04718ba4c2028` is an ancestor of that head.
- The complete base-to-head diff has 180 paths: one production source file, five test files, 17 handoff/check JSON packets files, and 157 evidence files. All six product paths match the pinned census; no hidden production or release companion appeared.
- This is not a fast-forward from G: G and A diverge at `198076863e143dea9f89f02734b13d50dae3eed5`; neither G nor slice base is an ancestor of the other branch/head. The candidate remains an exact history-preserving merge decision, not a cherry-pick/fast-forward assumption.

## New product delta

`4ef715efc89865325b789eed3ccd340da7b9f3be` (parent `ec5d9b0308b94d439d16eb900990cdc880f12547`) changes exactly two paths: the A-owned canonical writer `generation_cycle.py` (blob `e3c369a8a40db0849db4bb08ca732fd7c5761fa7`) and its `test_emp_01.py` companion (blob `284f373c87eb7212aaf8bc9d67a1a3fcbb34e203`). The code binds content-verified N5 results to their actual supported schema/version and the test adds a v2 positive plus foreign/tampered-reference refusals. Those blobs are unchanged at A head 332.

None of the 17 committed handoff/check packets names 4ef or the 332 tree as its product candidate. All 23 runner receipts pin 10 earlier candidates; none targets 4ef or 332. The adjacent source-review ledger is unchanged from base and its newest reviewed candidate is 1a520, while the narrow context-guard review pins 85bf and its test candidate 12ea. These reviews/receipts do not establish execution of the new version-mapping delta. **Exact run and updated committed handoff required for this new property.** No tests were run by this reviewer.

## Receipt integrity and limits

All 23 `receipt.json` candidate/tree bindings resolve to real commits and matching trees. Their 121 runner-output aliases match recorded SHA-256 and byte lengths exactly; 13 additional evidence files are directly path/hash-bound by their handoffs. Thus all 157 new evidence paths have a verified identity binding. This includes stdout/stderr/JUnit/origin/receipt copies and the large physical-cache input-provenance snapshots; raw output was not rewritten.

The receipts retain mixed results: the B23 physical-cache positive run is green and both input-removal falsifiers are red; the B11 scheduler positive is green, while its removal control is red; B11 artifact readback's combined command is red with three EMP-01 cases failing and its specific B11 projection node passing; the fallback aggregate remains red although its two target cases are recorded as passing; K_sim raw attempts remain FAIL/ERROR/FAIL with an independent bounded reconciliation; context-revision aggregate attempts remain non-green. Keep these as exact property/attempt results, not one package-level “pass.”

Among these 17 new A packets, B23 alone carries root acceptance for the original bounded invocation-local physical-cache criterion. G adjudication remains separate. B01–B03 remain limited because production source bytes/content are recorded `MISSING` and the three served checks are `UNRUN`; this audit did not inspect production data. B06–B07 remain formally pending, B09/B11/B27 remain limited/open, and the K_sim refusal is a bounded witness rather than closure.

See [pins.json](pins.json) for the immutable pins. The detailed per-packet audit index remains ignored local evidence: `policy-engine/_build/e02-g-continuation-20261006/R/A-332-20261007/identity-receipts.json@sha256:53c152e31d592d5fa21f0492307614c0605eef292571d287445d7cd2cd15fb05`; the original packets are read from the exact candidate Git tree.
