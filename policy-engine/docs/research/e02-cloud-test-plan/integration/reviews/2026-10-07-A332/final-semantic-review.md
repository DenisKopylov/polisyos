# A332 independent semantic delta review — final update

**Final disposition:** the semantic review remains bounded GO, but code admission is **HOLD**: the exact-candidate wave has one actual persisted-history failure, and whole A ancestry admission is still outstanding. Finding closures: **0**. This review did not run tests; the separate native receipts below were read back and verified.

## Pins and original review (historical, before native run)

- G review head: `2abc17f46a033a7879663486ff9946a95786601f`. A base/candidate/tree: `2605d13916f4dd38f216419562c04718ba4c2028` / `332ba0b91e9a85774d48d101d4af86e3a3baf911` / `4e21c90467913c6dae1c85b84b8c7a42a1dc9124`. The candidate is based on the declared base; base-to-candidate footprint is 180 paths (one production file, five tests, 17 handoff/check JSON packets, 157 evidence files).
- Commit `4ef715efc89865325b789eed3ccd340da7b9f3be` changes canonical A `generation_cycle.py` and an existing three-case parameterized test in `test_emp_01.py`. The v2 mapping is additive at the code-diff level; none of the owner handoff/check packets identifies 4ef/332 as its implementation candidate. That missing matching A handoff remains an admission gap, not evidence that the code is defective.
- **B27:** the original criterion requires an aligned revised context, successful permitted second iteration, and original/revised requests in shared saved history; it forbids simply disabling the equality check. The guard is a conservative typed stop. Its removal control reaches the existing N4 mismatch exception, not stale-context N5 execution. The positive criterion remains open; a hint-only false block remains a bounded limitation.
- **B11:** original criterion is low-proxy continuation while bounded budget remains, stop at true exhaustion, and no presentation of heuristic score as measured monetary VOI/probability; B66 settlement is separate. Prior consumer evidence uses a manual lease callback and only negative HTTP 409/403 content outcomes. It does not establish ordinary worker production, a positive public inspection, or spend. Treat these only as gaps for claims that include those surfaces.

## Final native-result delta

The current [native checks](../../../../docs/research/e02-cloud-test-plan/integration/reviews/2026-10-07-A332/native-checks.md) and [tester report](../../../../docs/research/e02-cloud-test-plan/integration/reviews/2026-10-07-A332/native-report.md) bind all runs to candidate 332/tree above. I checked the compact receipt and all 51 output aliases: all files exist and recorded byte counts/SHA-256 values match. No G source/ref changed. The exact candidate outcomes are:

- Direct N5-v2 mapping and foreign/tampered-reference refusal: **PASS 3/3**.
- Default conditional simulation plus persisted history: **FAIL 1/1**, at `validate_generation_cycle_run_history(persisted)` with `generation_cycle_historical_projection_mismatch`. The preceding N5/N8 result and limitations were reached, but persisted history is not accepted. No exact slice-base replay was made, so introduction/inheritance attribution is `not_established`.
- Core fresh-manifest/CAS and HTTP refusal selector: first export omitted its fixed claim-dependency registry, so the raw FAIL is **UNRUN for product behavior**. The one authorized Core-only repair added the exact candidate 1,825-byte registry to the ignored export and passed **1/1**. Initial UNRUN is preserved separately.
- Final deciding total: **4 PASS / 1 actual candidate FAIL**. Four earlier harness failures are not product results. No broad suite ran.

The output manifest’s 51 entries were independently checked against local files (zero missing, zero hash/length mismatches). The ignored identity index now exists and matches its referenced SHA-256. The previously missing native report now exists, and the pack labels its 17 files as handoff/check JSON packets. These three earlier documentation corrections are resolved.

## Final owner and cleanup state

- Code admission stays **HOLD** on the actual history failure. Return the exact failing path to canonical A owner; keep P41 attribution `not_established` absent slice-base replay. Reconcile the full unaccepted A ancestry and accepted G/V11 content by an ordinary history-preserving owner merge; 4ef’s additive two-file diff is not a substitute for whole-history admission. No finding is closed by this result.
- B11 wording is now aligned across native checks, README, consumer review, admission, and the appended A prompt: the original scheduler/budget and honest-heuristic criteria stand. Ordinary-worker production and positive public inspection remain unverified only for claims that include those surfaces; they are not new B11 prerequisites. B27 remains open for a valid revised context, successful second N4/N5, and shared saved-history positive. Do not repeat the unchanged guard-removal probe.
- The isolated export `native-A/candidate` was moved to native Trash after its 77,930,496-byte allocated-size measurement. [Cleanup receipt](../cleanup-20261007/A332-export-native-receipt.json) records `verified_in_native_Trash`, source absent, and the same device/inode at `/Users/deniskopylov/.Trash/candidate`. The deciding outputs and Git source remain in their separate locations; Trash was not emptied.

## Earlier report corrections

The pre-run snapshot’s claims that native results were pending and the report link absent are historical only; the current results supersede them. The earlier native-report, identity-index, packet-count, and B11-scope wording corrections are now resolved. The identity index is available at `policy-engine/_build/e02-g-continuation-20261006/R/A-332-20261007/identity-receipts.json` (SHA-256 `53c152e31d592d5fa21f0492307614c0605eef292571d287445d7cd2cd15fb05`). The reviewer ran no tests or native checks.
