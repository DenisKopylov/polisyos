# R15 evidence index

R15 adds a compact evidence set for bounded local runs and current cloud returns. The complete allowlist and source/postimage hashes are in `LOCAL/raw/e02-execution-20261027/docs-progress-r15/r2/manifest.json` (the RAW locator is exact; it is not adjacent to this canonical index). This R2 successor contains 165 gzip payloads and 171 total canonical targets (the payloads plus six documents): 4,007,612 source bytes and 1,197,377 compressed bytes. Each payload entry binds source path, source SHA-256 and size, exact canonical target, absent target preimage, and compressed/uncompressed SHA-256 and sizes.

- [R15 progress](progress-r15.md)
- [Machine-readable R15 state](progress-r15.json)
- [C60 executable/cache](cases/c60-executable-cache-r3/)
- [C95 fresh-process triplets](cases/c95-fresh-process-r4/)
- [C60 strict clients](cases/c60-strict-clients-r3/)
- [C105 focused native results](cases/c105-native/)
- [FED R5 scope/restore commands](cases/fed-r5/)
- [Cloud launches and independent return reviews](cloud/)

No cache, CAS/DB, full basetemp, source frame, duplicate R13/R14 payload, or candidate diff is copied. R2 removes exactly 20 C95/FED per-command JSON copies already present as equal subobjects in retained outer audit JSON; the exact JSON pointers and equality receipts are in the R2 manifest. The R1 packet is preserved unchanged. R2 references the remaining 165 R1 payload files without duplicating them. The C60 strict-client folder includes its exact positive and negative client inputs, invocations, and complete mypy stdout/stderr; its raw one-case PASS awaits independent qualification. C95 includes every worker record, stream, JUnit and source readset. C105 and FED outputs remain bounded to their named cases and own source cuts.
