# Welfare draw validator C901 delta

This follow-up records a private structural change to `welfare_draws.py` after the
earlier Welfare decomposition receipt. It does not change Monte Carlo draw, retry,
terminal-status, or numerical-summary semantics.

## Change

The original `_validate_monte_carlo_draw_set` measured at C901 complexity 15 against
the existing limit of 12. Its checks now delegate to private helpers in the same
module for count reconciliation, outcome and retry identity, successful-sample
indexing, and value-array reconciliation. The request denominator and terminal
partition checks remain in the validator path. No C901 exception, rule limit, public
API, schema, or numerical policy changed.

The test adds a valid retried-draw call through the validator and two remove-property
controls: a changed retry input digest and a missing terminal row must be refused.

## Current source and verification

| Path | SHA-256 |
|---|---|
| `src/polisyos/scientist/nodes/builtins/simulate/welfare_draws.py` | `83ec5549ba121370e2ec694c41ed1bb9c5b712a01cc12ae61d80ea497dfbecb7` |
| `tests/unit/scientist/nodes/builtins/simulate/test_welfare_draws.py` | `a3ba785a8b6b34100f29d499c7d71dac1c544aa442345451cdb528c04e254430` |

`welfare_draws.py` is 913 logical lines under the existing 1,000-line ceiling.
The fresh C901-12 check passed across the exact 32-module implementation set used
by the current native decomposition review. Its fully expanded argv, input hashes,
stdout, and stderr are recorded in
`LOCAL/raw/welfare-current-review-delta/c901-full32-final-after-format.command.json`
and the sibling `c901-full32-final-after-format.{stdout,stderr}.txt` files.
The full stdout is `All checks passed!`; exit 0.

The focused draw selector passed **4 tests**. This includes bounded same-draw retry
accounting, direct acceptance of the retry-bearing draw set, rejection when a retry
uses a changed sampled-input digest, refusal when one terminal outcome is removed,
and the global-permission failure control. Full output:
`LOCAL/raw/welfare-current-review-delta/pytest-draws-final-after-format.txt`.
Focused Ruff check and formatting check both exited 0; outputs are
`ruff-focused-final-after-format.txt` and `ruff-format-final-receipt.txt` in that
same raw directory.

The earlier `LOCAL/raw/welfare-current-review-delta/ruff-current.json` remains an
unchanged source-free Ruff receipt for the pre-refactor source hashes. This delta's
fresh lint, complexity, formatting, and behavior receipts are separate. No release
fragment was added because this private complexity refactor changes no operator-
visible or compatibility behavior.
