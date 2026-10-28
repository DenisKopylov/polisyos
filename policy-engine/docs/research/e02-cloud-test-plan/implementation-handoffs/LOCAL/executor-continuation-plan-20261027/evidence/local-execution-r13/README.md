# R13 evidence index

The canonical evidence delivery is rooted at [`cases/`](cases/). It contains the selected lossless gzip outputs for these seven local cases:

- `cases/c48-fixture-coherence-two-r3-20261028/`
- `cases/c60-canonical-cli-local-r2/`
- `cases/c60-strict-abi-defining-r4-20261028/`
- `cases/c60-type-pilot-local-r3/`
- `cases/c60-types-rest-local-r3/`
- `cases/c71-authenticated-source-post-r3-20261028/`
- `cases/c71-c86-cheap-components-r3-20261028/`

The exact 94-target delivery set and per-file preimages, hashes, compressed/uncompressed byte counts, and source bindings are in `LOCAL/raw/e02-execution-20261027/docs-progress-r13-r2/delivery-allowlist.json` (SHA-256 `9d5adf556e98e5d64b99b4528f660f6ebae4de41f12f9ed048786eb6b314abf1`). R3 reuses that allowlist without duplicating payload bytes. The four C60 defining-child files are the exact invocation, stdout, stderr, and input client named in the allowlist.

R3 records a bounded C93 focused native PASS of 139 selected cases at source commit `ef7ea1ab5cc159d88b73ae19acde9a781ae37453`, qualified only for that finite set. The 25 controls, cold/full run, full 147-case suite, and G acceptance remain unestablished. The source cut for earlier run bindings remains `24a7b01e85e613fcd7bc789bca9fead6f38846d7`.

The actual R9 publication/readback receipt is `LOCAL/raw/e02-execution-20261027/publication-composed-progress-r9/remote-readback.json` (SHA-256 `3c9836e5e1854ddd243f9a5c259df468176f11ec46547ff4f4b7e266e72b1edd`), covering source `ef7ea1ab5cc159d88b73ae19acde9a781ae37453` / tree `e5f9294b3fafecc550bfd700819ae4db0919502e`. This receipt establishes that publication; it does not establish publication of this R3 documentation proposal.
