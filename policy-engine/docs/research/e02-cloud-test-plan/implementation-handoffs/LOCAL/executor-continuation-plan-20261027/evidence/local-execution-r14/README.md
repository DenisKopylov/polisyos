# R14 evidence index

This proposed canonical evidence root contains only selected complete deciding outputs for five new local case results. Exact source/origin hashes, compressed and uncompressed hashes and sizes, absent-target preimages, and exclusions are in the complete `LOCAL/raw/e02-execution-20261027/docs-progress-r14-r3/evidence-allowlist.json` (SHA-256 `dcf5360fd788c6fdc7addb91d6a575b4bef01f7f9681d862339ea6b2d1f25343`). The allowlist is retained in RAW; it is not adjacent to this proposed canonical index.

Case roots:

- [`c60-five-canonical-cli-local-r4/`](cases/c60-five-canonical-cli-local-r4/)
- [`c60-five-types-local-r4/`](cases/c60-five-types-local-r4/)
- [`c60-provider-closure-defining-r5-20261028/`](cases/c60-provider-closure-defining-r5-20261028/)
- [`c60-typing-fusion-compatible-r1-20261028/`](cases/c60-typing-fusion-compatible-r1-20261028/)
- [`c95-canonical-nine-controls-r1-20261028/`](cases/c95-canonical-nine-controls-r1-20261028/)

Payload totals: 75 gzip files, 619,288 uncompressed bytes, 194,585 compressed bytes. R3 adds 12 deciding child files (23,496 uncompressed bytes) from two existing C60 actual results: four provider-closure defining-mypy inputs/outputs and positive and negative typing/fusion child invocations, clients, and complete streams. These supplement existing results; they do not create new case outcomes or change PASS/FAIL status. The original 63 payload bytes are reused by immutable reference; no R13 evidence payload is duplicated. The delivery excludes all other basetemp content, caches, CAS/DB, source frames, complete profile/readset copies, and process-wide/event logs.

The R13 payload roots and published readbacks remain available under [R13 evidence](../local-execution-r13/README.md). R14 documents the five new bounded actual cases; it does not broaden any result to G acceptance or closure.


## R14 R2 current plan stage

Wave 2 owner composition is the main current stage. Wave 0 is done; Wave 1 executed with open properties; Wave 3 has targeted preparation only and no full freeze; Wave 4 final G review has not started. Row-by-row original status remains in [QUEUE.json](../../QUEUE.json), with [PLAN.md](../../PLAN.md) and [LAUNCH.md](../../LAUNCH.md) as the wave/launch map. `Cnnn` names point to evidence for those original rows only.

R14 R1's 63 payloads remain byte-for-byte reused by reference. R3 adds only the 12 listed deciding child artifacts and records a cumulative 75-file allowlist. R2 added no payload copies. The source cut remains an as-of snapshot, not a later remote publication.


## R14 R3 evidence-delivery correction

The R2 independent audit verified the original 63 gzip files but found that blanket exclusion of `basetemp` had omitted 12 finite deciding child files bound by actual independent review receipts. R3 adds exactly those 12 files. They are stored under the existing five case roots in `deciding-child/`; no other basetemp content, cache, full child tree, source frame, CAS, DB, or run is included. The exact merged 75-target inventory is in the R3 RAW allowlist linked above.
