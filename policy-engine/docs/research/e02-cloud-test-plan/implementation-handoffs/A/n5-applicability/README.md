# N5 applicability handoff artifacts

`../n5-applicability.json` is the handoff receipt. This directory holds the exact moderate evidence files cited by it.

- `runs/b10-red-0b558/`, `runs/b10-red-import-fixed/`, `runs/b10-green-bf465/`, and `runs/b10-typed-money-wave/` retain all four files from each earlier attempt.
- `runs/frozen-consumer-wave-6565-corrected/` retains the final exact-candidate frozen wave: environment/input manifest, stdout, stderr, and JUnit XML.
- `runs/selector-preflight/preflight-error.json` is the separate non-product input-path preflight error; its record explicitly says product runtime did not execute.
- `diagnostic/` contains the exact prior Decimal typed-request diagnostic stdout/stderr.
- `independent-review-and-census.md` carries both independent review texts and the full complete Decimal leaf census, with source path, SHA-256, and byte count.

No pytest basetemp/CAS files or derived inventories are copied. Empty stderr files are preserved as zero-byte files and their SHA-256 is recorded in the receipt. The final check is tied to source commit `6565fcd91d0ac251396dbde5852aaad92627bf40`, tree `a1177b8113e1b75973e7975f6809553c38e65b52`. The B10 criterion remains `partial` / `verification_missing`; this bounded conflict-preflight witness does not run the canonical “first candidate lacks needed input, second has it” acceptance scenario.
