# P41 relocated JUnit artifact receipt

At the append-only broker checkpoint snapshot inspected on 2026-09-24, 113
file/base rows had been recorded. Four safety-skipped `test_data_state_substrate.py`
rows had no JUnit by construction. All 109 JUnit references were found with
their recorded SHA-256: 61 at the original paths and 48 in the prior run's
relocated `PolicyOS_E02R2/raw/<run-id>/cells/` directory. The complete
113-row inspection verdict is **PASS** for artifact byte identity; no JUnit
reference was unresolved. This is a snapshot of an in-flight checkpoint, not
the final baseline verdict or a test-semantics conclusion.

Input and full 48-row path remap: `/Users/deniskopylov/.codex/scratch/e02-r2-p41-artifact-remap-20260924.json@sha256:4f0e2848ec8f83079cc9b20bcbb29aeee90c51d73f3b8cb2d616dad4b9b907be`.
The receipt records the exact checkpoint path and SHA-256 it read, the raw
artifact root, each old and relocated path, and each JUnit SHA-256. It
examined every checkpoint row, not a sample.

The prior stopped run's scratch directory moved after checkpoint reuse; its
JUnit bytes remain under the gitignored package `raw/` directory. A stale
scratch path is therefore a path relocation, not missing test evidence. The
broker had verified these rows' JUnit content before reuse. For final P41
reporting, cite the relocated byte paths and re-run the complete artifact
inspection over the finalized checkpoint. A future row appended after this
snapshot is unresolved by this receipt until that final inspection.

The relocation check only proves JUnit byte identity. It does not determine
which cases pass or fail, whether a case is environmental, or whether a
finding's distinguishing property was tested; those remain the baseline
broker's and finding owners' separate obligations. Its three-valued
inspection outcome is `PASS` here. A confirmed absent or SHA-mismatched
artifact would make artifact custody `FAIL`; an exception that prevents the
inspection from completing would be `UNRUN`. Neither outcome is an inferred
test failure.
