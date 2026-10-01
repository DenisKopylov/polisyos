# R14 canonical N9 negative-source witness checkpoint

## Discrepancies and measurement boundary

The current 15-case whole-file baseline at `8b40f8f5a8d838235a22b92e6f9adc84f006e551`
completed with 14 passed and 1 failed. The failing case is
`test_persisted_eval_safety_source_blocks_terminal_n6_before_n9_receipt_read`:
its selected source context was `not_established` instead of `established`.
The older four-base 14-case file did not contain this case. This current-head
baseline establishes neither inheritance nor a passing patched suite.

Root reconciled all 15 JUnit identities, every JUnit/stdout/stderr hash,
origin audit and unchanged source fence:
`/Users/deniskopylov/.codex/scratch/R14_CURRENT15_ROOT_RECONCILIATION_20261001.json@sha256:6e869fdf5cb22d54c19c54bb6a9fc2da679737c69609e9eeec86e0231c2c24cc`.
Raw result:
`/Users/deniskopylov/.codex/scratch/e02-r14-current15-baseline-20261001/r14-current15-20261001T051040Z-12440-b154d950/result.json@sha256:92e91635fc0b284b8751f2ee108847368b9e118848ba6a8b2b313294be410a43`.
The origin audit passed over 10,022 frozen inputs with zero drift. Wall time
was 58.988 seconds, peak group RSS 1,006,608 KiB, minimum free RAM 56%,
swap growth zero and minimum free disk 11.07 GiB; no resource guard fired.

## Applied property and review

The test now uses one existing EvalSafety fixture owner and store for intake
and persistence. An actual controlled nonblocked N6 run obtains the canonical
N9 owner's `not_promoted` observation and replayable receipt. The selected
compiled source is persisted and consumed by `compose_and_persist_attempt`.
The persisted source-resolution record must bind that exact compiled ref,
and the persisted decision must retain `promotion_safe_facet=False`.
The genuinely blocked N6 twin must still refuse before receipt parsing.

P27/P29/P38/P40: this repairs a source/consumer witness gap in one test file;
it introduces no runtime mechanism, fabricated terminal status, handwritten
authority receipt or production promotion claim. `near_miss=False` is a
fixture control; the decisive property is the consumed negative promotion
facet. Automatic production N6-to-N9 dispatch and S8 authority remain unproven.

Reviewed patch:
`/Users/deniskopylov/.codex/scratch/e02-r14-case9-n9-negative-source-candidate-20261001/R14_CASE9_N9_NEGATIVE_SOURCE.patch@sha256:0bba246f8cf6a6c1735833997975c359b6e63933cf1ecfd05e2fbc807d061deb`.
Root readback of the applied test matches candidate SHA-256
`f56f1239f79fbc3c22d9fea856df05adf00bc9006e48c3b445c450c82a4c6ffd`.
Independent static GO:
`/Users/deniskopylov/.codex/scratch/e02-r14-case9-n9-negative-source-candidate-20261001/R14_CASE9_INDEPENDENT_STATIC_REVIEW.md@sha256:0c9c8ef965fda23b4180e366b58d74709eeeee7a18f24eb9074027d6c7cb85d1`.
Its baseline path was transcribed incorrectly; the raw result path above
is the actual root-verified input. Ruff on the sole changed test file passed.

Post-integration whole-file replay is **UNRUN** at this checkpoint. No ledger
status or R14 class closure follows before that replay.
