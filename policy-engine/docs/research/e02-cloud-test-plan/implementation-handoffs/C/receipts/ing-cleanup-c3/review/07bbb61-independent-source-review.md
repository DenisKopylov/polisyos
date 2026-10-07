# Independent review: stream cleanup-owner transfer

- Candidate: `07bbb61ffa6d53709942bcda87c37daef1a04651`
- Tree: `4bb3d7ef227f7745ab22a23f41f4618766e8b350`
- Parent/base: `c158689d692d47b6300609ac2ba5e7dac28650dc`
- Branch readback: `codex/e02-C-continuation-20261006`, clean at review time
- Review scope: exact source/test diff only; no test suite or removal probe run by this reviewer.

## Verdict

**GO for the bounded C production cleanup-owner property.** This is the same P40 cleanup-owner-transfer class widened to the shared close invariant, not a new B API. No C-to-G admission or combined-runtime claim follows from this candidate review.

`StreamingSourceSession.create` retains the resolved registry on the session. `close` now wraps `close_stream`, `pool.release`, and `pool.close_all` in one `BaseException` recovery boundary. On failure or cancellation it leaves the session retryable, marks cleanup pending, and transfers the same pool to the registry retry owner. Startup cleanup uses the same transfer method. The concrete registry stores that exact pool and retries it; its owner entry is removed only after `close_all` succeeds. The pool preserves the physical handle and only returns a permit when the pool confirms cleanup.

## Behavioral coverage read

The new test file has six parameterized executions across five scenarios:

- Primary sanitizer `RuntimeError` and `CancelledError`, with exact primary exception object identity preserved while final disconnect and the first registry retry fail.
- Successful stream processing whose final physical disconnect fails; the persisted checkpoint remains closed and committed while the error is surfaced and the registry retains the pool.
- Actual `Task.cancel()` after the real JSONL connector yielded a chunk, with registry retry of the same physical handle.
- Crash-before-frontier-commit refusal: the prepared checkpoint and partial chunk remain unchanged; no extra source read, cursor, or window is admitted on retry.
- Crash-after-frontier-commit reopen: exact raw rows and order, chunk IDs, window order, contributor refs, final checkpoint, and cursor are read back from CAS.

The cleanup cases assert pending permit `False` and one free semaphore slot before retry, after a failed retry, and after successful retry. That is the correct invariant for this path: `release()` first returns the handle to idle and releases its permit; `close_all()` then fails disconnecting that idle handle. The registry retries the same handle without releasing a second permit.

## Bounded limitations

Directly constructed `StreamingSourceSession` instances with no registry remain caller-owned; the repository production path through `process_stream_dataset` passes the resolved registry. If the registry's own synchronous in-memory retention insert raises, the helper adds a note to the primary error and cannot transfer ownership elsewhere; the concrete insert has no ordinary failure path, so this is a bounded fatal resource failure.

The two frontier “crash” cases raise a `BaseException` at the commit seam, but Python `finally` still runs; they demonstrate persisted-state refusal/reopen semantics with fresh store/cursor readers, not OS process isolation. Do not describe them as a hard process-death test.

The parent reports a property-removal control that removes only the retention-helper call and fails all four owner assertions, plus fresh targeted-suite receipts. Those runs were not independently repeated in this review.
