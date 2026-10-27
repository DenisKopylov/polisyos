# E02 detailed remainder and completion plan

This packet records the detailed assessment of the 19 previously unfinished tasks at the pinned a92 source cut. I1 is newly ready for G at its bounded author task exit; 18 tasks retain work. The plan has begun execution through separate reviewed implementation packets. Source acceptance and finding adjudication remain with G.

## Denominator and scope

- The original manifest has 26 task/decision rows over 127 bundles, 282 unique findings, and 291 criterion occurrences.
- This packet covers 19 task report rows. I1 is author-complete at its bounded task exit; 18 rows retain implementation or verification work.
- DEC0 is separate from these 19 task rows. Six other bounded task rows (BOOT0, T1, R2, R4, I4, V6) are not re-opened by this packet.
- Q0 directly owns 206 finding IDs across 212 criterion occurrences. The other 76 IDs / 79 occurrences are routed to specialist rows. Q0's 291-row navigation/source-cut inventory does not provide 291 current semantic outcomes.
- Formal finding closures proposed here: none. Each row keeps closure_ids empty; G admission remains separate.

## Files

- PLAN.md: execution order, leases, constraints, acceptance criteria, and all 19 row summaries.
- tasks.json: machine-readable original exits, current report-level status, remaining units, exact test proposals, resources, and report SHA-256s.
- Source task reports and correction addenda remain beside this directory under ../raw/remaining19-detail-20261027-r1/<TASK_ID>/report.json and are cited by path and SHA-256 in tasks.json.

## Source boundary

Product work is pinned to a92c9774edf8049d590cd6ca6de35aa17063025a (tree 7f9908cd38ca5aa2148f7cc9458d3dbbd0cdb1d9). At the pinned packet-generation snapshot, HEAD 65ac853e2735e827e27688a6175f1a385901e20e includes BOOT0/T1 integration documentation and an R2 regression-test commit that adds tests/unit/fabric/connectors/test_pool_admission_races.py (two passing nodes per root). At that commit the committed product-src diff from a92 is empty; this does not describe subsequent dirty first-wave postimages. This packet makes no product-source or finding-status changes.


The source cut is explicit: later packet commits and first-wave changes do not turn historical or source-only evidence into fresh runtime proof. See verification.json for report identities, corrections and independent review.
