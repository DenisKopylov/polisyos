# DDM r19 neutral-import and legacy-event removal controls

## Result

This receipt executes exactly the two requested triplets from pinned commit
`aa8571cba044ebe04d4db4f99432cb49abdde59a` (tree
`0ff45c87431af2a4139519ff31d123ff465ed862`):

| Control | Baseline | Exact mutant | Byte-exact restore |
| --- | --- | --- | --- |
| N — neutral `polisyos.ddm.contracts.events` | PASS | SEMANTIC_RED | PASS |
| L — synthetic old event FQN cold reader | PASS | SEMANTIC_RED | PASS |

Control N's complete mutant child report has an empty pre-import first-party namespace,
the sole trapped attempt `polisyos.ddm.integration.monitor`, and the expected
`RuntimeError` beginning `LIVE_DDM_IMPORT_TRAP:`. Control L's complete mutant reader
report sees `polisyos.ddm.integration.events.ShiftDetectedEvent` and raises the expected
`AttributeError` because that export is absent. Its mutant and restored phases reuse the
validated baseline inner writer record exactly (1,345 pickle bytes, SHA-256
`66083e3804228ba12bda0e5d41a32ffdf993311b5a18b846feebada9b6bf0306`) and contain no
writer subprocess.

## Evidence map

- `receipt.json` is the compact adjudication: source identity, selectors, pin admission,
  phase/run bindings, mutation hashes, semantic causes, writer reuse, origin/readset
  location, P29/P33/P38/P41 classification, final control-tree state, and boundaries.
- `evidence.tar.gz` losslessly contains every deciding run's complete stdout, stderr,
  JUnit XML, all five per-PID observer files, argv/profile/timing and source/index
  pre/post records, as well as admission and environment inventories.
- `archive-manifest.json` records the archive hash/size and every member's hash/size after
  reopening the gzip/tar stream and fully reading every regular member.
- `build-receipt.py` is the exact temporary collector/adjudicator source used to validate
  child semantics, local origins, PID/cache/bytecode facts, writer reuse, clean final
  controls, and to create/read back the archive. The direct phase runner is retained
  inside the archive as `run-phase.sh`.

The source checkout was read-only. The two controls ran sequentially in physically
separate detached worktrees, and neither temporary mutation was staged or committed.

## Scope boundary

All payload, event, model, writer, and pickle values are synthetic and diagnostic. This
slice establishes neither historical writer-byte availability nor calibration,
authority, promotion, production-model evidence, whole-LA-056 acceptance, or G closure.
It is not a broad-suite result. `verification_missing` remains pending independent review
and broader criterion adjudication.
