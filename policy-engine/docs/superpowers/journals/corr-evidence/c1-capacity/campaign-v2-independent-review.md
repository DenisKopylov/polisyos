# Campaign v2 bounded independent review

The fatal stop/recovery/history delta is accepted on the bounded evidence below.
This is a source review of the existing checkpoint owner and its dedicated
recovery tests, not a claim that the future full-corpus run has executed.

The initial review found one concrete **same-class deeper temporal boundary**:
a later-dispatched call could fatal-fail, be recovered, and then an earlier
in-flight call could fatal-fail after that recovery. Dispatch-sequence filtering
would hide the late result. The repair widens the sole `recover_fatal_stop`
intake: any `state=dispatched` refuses recovery. Once prior admissions settle,
explicit recovery cites the actual active stop and preserves all attempt records
and consumed budgets. The public API now supplies this invariant independently
of the CLI process lock.

The historical reader retains the original plan projection and complete
input/attempt/work bindings. It uses the existing shared checkpoint lock and a
bounded stream copy of DB/WAL metadata into a separate disposable view. The
original DB/WAL/SHM identity and byte-hash projection is checked before copying
and after reading. SQLite may build its disposable SHM only in that view. No
current owner hash is substituted into the historical plan, and dispatch/write
operations remain refused. The graph finalizer can consume these original work
outputs under an explicitly historical input epoch.

Deciding evidence:

- `campaign-recovery-quiescence-red.json`: actual public API red, RC1, 1.875s.
- `campaign-history-wal-red.json`: actual valid uncheckpointed WAL refused by the
  earlier view, RC1, 1.793s.
- `campaign-recovery-wal-green.json`: the exact two targeted tests pass, RC0,
  1.748s, after the shared recovery/view corrections. Full argv and streams are
  retained in that record.

The later added disposable-view provenance/cleanup assertions have been read
but are **not_established by this receipt**; they await the author's final
focused wave. No heavy/native tests were run by this reviewer during the
provider throughput quiet window. No second blocking finding was found in this
delta. New CLI finalize/recover wiring and graph finalization are reviewed and
verified separately.

Verification append: `campaign-history-marker-green.json` subsequently executed
the exact history/WAL case with the added own-provenance and cleanup assertions,
RC0, 1.880s. That closes the specific verification limitation above. The author
also reports the complete campaign/recovery regression identity reconciliation
at 21/21 and three decisive removals; this review's independent receipt readback
is confined to the named two-node and history-marker captures.
