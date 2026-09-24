# GY builders B journal

Task `GY-CR1`; base `07c89304d`; branch `codex/gy-builders`.

Stage 1: read GY full Phase-8 definition, OPS-R5 §7–8 and `FM-OPS-12/13/16`, `WP-08`,
CONTRIBUTING, failure/repair register and existing persistence/authority owners.
Decision: `../specs/2026-09-10-gy-builders-b-decision.md`.

Executed owner census and real SQLite reopen/duplicate/checkpoint probe:
`PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m docs.superpowers.journals.gy-builders.b.research`.
Complete receipt: `gy-builders/b/research.txt`; reproducible runner:
`gy-builders/b/research.py`. Source denominator is complete `src/**/*.py`, independently
enumerated by rglob and os.walk with exact identity-set reconciliation.
Result: **2,640 Python files by each independent walk**, equal identity sets, zero
unreadable files, and zero matches for each of the four requested artifact names.
The real reopened store preserved request identity and checkpoint state; same-key
different-content returned the original row; HTTP pending reservations were local.
RC 0, cold startup approximately two minutes. The initial direct-owner import failed
on an existing import-order cycle (`gy-builders/b/research-cold-import-failure.txt`);
initializing the existing `runtime.http.services.control` composition root before the
direct store import passed. No executed owner was repaired.

At Stage-1 closeout, Stage 2 had not begun. Root serializes commits and shared README/facade changes;
`runtime/http/services/control_plane_store.py` is reserved exclusively to B for the
minimal public outbox lookup seam. No production or test source was changed in Stage 1.

**Refused claim:** a protected response is not authorized; the planned consumer
requires a typed empty signer and terminates `failed_safe` naming its missing role,
while retaining conservative posture and escalation clock (`WP-08`, `FM-OPS-16`).

Default architecture gate: `not_completed` because its compiler chain invokes the
prohibited debt/ledger checker. No passed/skipped credit is claimed.

Stage 2 released after root committed/read back decisions at `c628361c5`.
The first required negative ran red with `CR1 durable candidate runtime is absent`:
`gy-builders/b/raw/wp08-red.txt`, RC 1. It tests the desired failed-safe missing-role
consumer behavior and fails before source implementation.

Before editing the store, research found its dotted module identity marked decisive
in `layer3_gy_confidence_ledger_contract.json`. The architect approved consuming its
existing internal exact-key reader instead. The planned store edit is withdrawn;
no governed owner bytes or epoch are changed. The B decision records this amendment.

Initial implementation verification: `mechanism-green-attempt1.txt` RC 0 (the
original eight falsifiers); `verify.txt` RC 0, **11 passed** across the complete
then-current named CR1 test file plus the one named existing outbox-owner test.
`removal.txt` RC 1 because removing the decisive content comparison makes the
unchanged conflict negative report `DID NOT RAISE`; the source is copied only into
ignored scratch and the tracked implementation is unchanged. `cli.txt` RC 0 executes
the actual package `-m` worker, then cross-checks one SQL custody publication against
the complete CAS decision identity set. `ruff-final.txt` RC 0.

Review bucket: **NEW class, temporal projection (`P08`)**, found before closeout.
A snapshot could project decision publication after its `as_of`, and restart evidence
had no availability/expiry disposition. Widen once across request observation,
decision publication, restart receipt/observation and expiry: future facts fail
closed; expired evidence stays a labelled historical candidate. This is a CR1-owned
repair, not an existing-owner change. The temporal negative is recorded before its
mechanism change in `temporal-red.txt`.

`raw/verify-final.txt` proves the temporal tests green and records a distinct failure:
**NEW class, concurrent CAS ownership-index mutation**. Two independent CAS owners
lost a candidate ownership entry before outbox admission; this run is not credited
as final green (`1 failed, 12 passed`). The repair serializes only CAS put/readback
using the existing `fabric.io.atomic.file_lock`. The shared resource and bounded
foreign-writer residual are declared in the decision. CAS and control-store source
remain unchanged. Subsequent fault receipts print actual PID, SIGKILL return code,
ticket, and complete SQL/CAS publication identities.

## Completion

| Task | Status | Deciding evidence | Binding falsifier |
| --- | --- | --- | --- |
| `GY-CR1` | `executed` within the declared candidate-custody/local-root scope | `gy-builders/b/verify-closeout.txt`, RC 0: 13 passed (12 cases in the explicitly named CR1 file, plus the one existing outbox test); actual SIGKILL PIDs/exit codes and exact SQL/CAS publication sets are run-emitted | `raw/wp08-red.txt` first red; final missing-signer terminal names `appointed_policy_rollback_authority`; actual killed worker and duplicate never repeat the own custody publication |

Final source: `src/polisyos/runtime/quality/adaptation_transition.py`; its four
requested candidate artifacts are persisted and read back through existing CAS,
and the package worker connects request → durable outbox → failed-safe decision →
checkpoint → audit snapshot. Restart evidence remains bound candidate material.
The two real interruption points are `_read_request` (durable request, before
processing) and `_checkpoint` (decision publication committed, request checkpoint
not yet committed). Both children exited `-9` after the parent's actual SIGKILL;
each reopened run and actual duplicate reconciled one complete SQL decision set
with one independent complete CAS decision set.

**GY-CR1's protected-response authorization claim remains refused: null-only
signer and after-hours substitute slots, a canonical shadow `AuthorityBoundary`,
and null-only/false-only fields at revalidated consumer intake enforce a
`failed_safe` decision naming the missing institutional role; escalation and restart
evidence cannot authorize or reopen it.**

Additional complete deciding receipts: `cli-final.txt` RC 0 for the real `-m`
package worker and independent custody readback; `removal.txt` RC 1 for the expected
unchanged-negative failure after removal of content reconciliation;
`ruff-frozen.txt` RC 0. Earlier attempts are preserved as history, not presented
as final green. The temporal red and all failing discovery receipts remain beside
their repairs. Expected warnings are retained: real fork in a loaded process,
Pydantic serialization of a deliberately forged signer, and pytest plugin rewrite
warnings from supported composition-root initialization.

Receipt identities are recorded compactly in `gy-builders/b/receipts.sha256` as
`path@sha256`; each small deciding output is retained completely. The initial
10.8 KB complete mechanism red is retained locally as
`gy-builders/b/raw/mechanism-red.txt@307b4ea9541a228d5d8164d2ad3c330ab3a2b8be30037b61cbaba3ee3a1de08e`.
It is ignored raw evidence, not a second tracked copy of the tests.
`raw/wp08-red.txt` and `raw/verify-final.txt` also remain complete and are cited in
the manifest; pytest's original trailing whitespace is preserved under ignored raw
storage instead of being silently edited to satisfy the patch whitespace gate.

`governed-owner.txt` RC 0 walks **520 `architecture/**/*.json` files** by independent
rglob and os.walk identities, with zero unreadable/ambiguous members. It reconciles
**2,017 `member_kind=source` dictionary occurrences** against independent literal
occurrence counts, finds the exact decisive dotted control-store member, and
proves control-store, CAS ownership and Fabric atomic-lock source bytes unchanged
against the lane base. This is a recorded-member census, not an inferred transitive
closure claim. No existing governed epoch was reissued by B.

Pattern register reopened before closeout: `P01/P02/P05/P08/P09/P27/P29/P37/P38`
govern this chain. No predecessor is replaced, so no StrangleReceipt is fabricated.
No institutional owner is appointed. All oversized scratch/CAS state stays under
the ignored `gy-builders/b/raw/` directory. Root performs the serialized commit,
branch readback, shared README and artifact-registry integration.

Routed residuals:

- `WP-08`: institutional signer and after-hours substitute stay
  `absent/unallocated`; no external execution or external exactly-once claim.
- `GY-CR2` owns constrained-product transitions; `GY-CR3` owns the independent
  response corpus/oracles. Their behavior is not credited here.
- Existing `core.artifacts.ownership.ArtifactOwnershipIndex` owns the foreign-writer
  residual: noncooperating writers bypassing the CR1 local CAS lock can still lose
  ownership entries. Routing rule `P27`; no debt-register edit is made.
- The existing `runtime.http.services.control` import-order cycle is an integration
  limitation routed to that owner under `P27`; the supported entry order is used.
- HTTP/Atlas presentation is `surface_out_of_scope`; audit snapshots and the CLI are
  the delivered surface. Historical snapshots before an already-published decision
  are explicitly refused; whole-history temporal reconstruction is not claimed.
- Default architecture gate remains **`not_completed`** because of the prohibited
  debt/ledger compiler chain. No directory-wide suite was run.

## Independent sibling reviews

A's full source/test/decision review found one **NEW class, current-use context
omitted from the semantic-owner bridge (`P02/P10/P38`)**. The original live witness
in `a-reentry-review.txt` made narrow and broad uses inside the same ceiling reach
the identical re-entry input. The approved batch binds immutable request, claim,
gap, resolved content identities, requested scope and evaluation time to both
verifiers and re-entry, also reconstructing them at audit read. The unchanged
independent witness now distinguishes the inputs (`a-reentry-delta-review.txt`),
and all nine named context-port/use-time-claim cases independently pass in
`a-context-nine-review.txt` (RC 0). The decisive semantic removal receipt was read
in full: substituting a permitted purpose while retaining markers causes the
unchanged independent-verifier refusal test to fail. Delta accepted within A's
declared candidate-only semantics; AS1 remains the independent oracle owner.

CB1's independent source/test/decision review found one **NEW class, decorated
stimulus bytes used as partition semantics (`P38`)**. Through the real corpus
owner, the entire input denominator was 40 items (8 training and 32 sealed): all
256 training-by-sealed pairs were examined and independently reconciled with
reverse byte enumeration. Each of the eight training stimuli appeared verbatim
inside its four sealed modality variants, yielding 32 matching pairs, while the
real owner admitted the corpus. `cb-partition-review.txt` retains complete output
and pins the original corpus hash. This violates the decision's content/family
separation without changing the false comprehension flag or withheld WP-09
bounds. Root approved a bounded structural-stimulus batch; its delta review is
recorded below. No broader review or institutional appointment is implied by this
finding.

The first delta's whole-family identity comparison exposed the **same partition
class one level deeper**: different current source stimuli in unequal declared
families can still share a member. Root and B independently identified this
boundary. The live `cb-partition-delta-review.txt` witness records actual admission
with one overlapping member before the approved widening. The final mechanism
compares complete unions of declared member bytes, with each current stimulus
required to belong to its family and displayed content derived from that stimulus.
The unchanged witness now refuses with `partition_leakage:source_family_member`
(`cb-partition-union-review.txt`, RC 0). The current 40-item corpus (8 training,
32 sealed) has zero exact-source reuse across the complete 256-pair denominator,
independently checked by reverse byte enumeration. The corpus is pinned by its
hash in both receipts. This delta is accepted within the stated structural scope.
Distinct-byte semantic paraphrase independence remains `not_established`, routed
to the unappointed W5-R3-Q06 adjudicator; that residual does not license a human
comprehension claim. No further breadth review or production edit follows.
