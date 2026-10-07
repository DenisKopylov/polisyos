# Six-root handoff identity for prompt routing (2026-10-07)

Read-only at G `ff277db7798fc312654704fa51c52e00f53f10f4`; exact input pins are `six-root-inputs.json`. All six head/tree, handoff blob/byte/SHA256 checks PASS. Candidate identities and complete counts are in `six-root-identity.json`@sha256:39da029f158b519c34afd90f42aee93f8dbf6ae4286f137dd6cb54af0f380871 (G-local ignored; full path view reconstructible from the cited Git refs). No code acceptance or finding closure is asserted.

**Review pin correction:** 2034 must use B coordination `456f34938731b1ef11555d8333d011d3552574ec` and D root `3c636ff52718897c9900a49580c9bd058086de35`. `b824930…` and `9cfe108…` are stale sixth-wave ancestors. The old 2034 topic heads `0d1f158…` and `8c17a44…` are ancestors of new `c683ab7…` and `828283e…`.

- **A:** Markdown handoff blob `35c0b944…`; source refs ffd6 runtime, 6f1e consumer, b3de companion match declared trees and remain ancestors. No new A source review.
- **B:** Root `c683ab7…`; receipt candidate `9260102…` is an evidence-only 36-path carrier off base `9622bb2…`. Code lineage is checked runtime `1862c02…`; affected-35 runtime `10e812a…` has matching source/test tree. New-vs-2034-root delta: 2,136 paths = 16 product Python / 19 test Python / 2,101 companions. Actual affected-35 run PASS; full and old affected runs ERROR/FAIL, cross-unit and quality FAIL; no formal closure IDs. Route source independently from the receipt candidate.
- **C:** Root and C54 source binding unchanged (`c158689…`, source `d50d28e…` off main base `1980768…`); tree/ancestry pass, 140 paths = 3/3/134. No semantic rerereview.
- **D:** Root `828283e…`; final candidate `258a6c8…` and engineering source `f2d5401…` off continuation base `cae5589…`; trees/ancestry pass. New-vs-old-root delta: 199 = 1 product Python / 6 tests / 192 companions. Only new product path is `run_hierarchical_policy_search.py`. Broad wave was SIGKILL / partial / no JUnit; 0 formal closures, G acceptance false.
- **E:** Root `e9cb425…`; nested final handoff binds numerical source `a9f7881…`; source-footprint delta 671 = 4/3/664. Keep prior HOLD/global FAIL limits; no rerun.
- **F:** Root/source unchanged (`072d45a…`, source `8236d9c…` off `421f1dd…`); identity pass, 2,944 = 40/51/2,853. No F rerereview.

Full new product/test path lists for B and D are in the machine record. Counts classify paths, not owners. The only bounded positive newly relevant is B’s exact 35-consumer result; it is not whole-B acceptance. D’s hierarchy bridge is a separate reviewable delta, but the current broad receipt is incomplete, so it is not ready to claim verified root behavior.


Publication scope: this is a pinned review observation/recommendation. A bounded GO here is not an integrated commit or formal finding closure. The root decisions in the eighth-wave README and newer per-unit audit take precedence for later heads.
