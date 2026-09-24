# GY builders B: durable candidate response custody

Stage 1 decision, 2026-09-10. Task: `GY-CR1`; lane base: `07c89304d`.
Owner: `runtime/quality`; related routes: `W5-S09`, `W5-O5-Q01`.

## Binding result

Build a durable response request, candidate operation charter, failed-safe decision,
restart-evidence custody, clock projection and exact audit readback. **The claim that a
protected response is authorized remains refused: the institutional signer slot is
`Literal[None]`, every record carries the canonical `AuthorityBoundary`, and the
consumer always emits `failed_safe` with the required missing signer role.** No
external executor callback is accepted. An operator/team string is not appointment.

This implements `GY-CR1` in GY §Phase 8 and the explicit build permission in `WP-08`
Activation. `FM-OPS-16` requires a declared conservative posture and an escalation
clock on absence, never approval; `FM-OPS-12` rejects appointment by owner string;
`FM-OPS-13` requires durable identity and dedupe. The full OPS-R5 §7.1/§7.3/§8.2
contract sketches supply candidate fields, not an action policy. `WP-04`–`WP-08`
remain withheld. Phase 8 is explicitly not gated by the phase chain and is the H2
custody runtime destination that lifts the recorded wave-6/7 research precondition.

## Existing owners and executed seams

Read owners: `runtime/http/services/control_plane_store.py`,
`runtime/quality/event_log.py`, `runtime/http/mutation_policy.py`,
`runtime/quality/agent_action_authority.py`, `runtime/http/services/control_worker.py`,
`runtime/quality/acquisition_route_loop.py`, `core/artifacts/store.py`, and
`pdc/_impl/layer2_readiness.py`, all under `src/polisyos/`.

The reproducible Stage-1 command is
`PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m docs.superpowers.journals.gy-builders.b.research`.
Its complete output is retained in `../journals/gy-builders/b/research.txt`; it walks
the complete `src/**/*.py` denominator twice (`Path.rglob`, `os.walk`), reconciles
identity sets, names unreadable inputs as ambiguous, and searches the four proposed
artifact names in every readable member. Runtime observations execute real SQLite
store instances across reopen, not mock implementations.
The result is 2,640 `src/**/*.py` files by both independent walks, exact set agreement,
zero unreadable files and zero matches for each of the four requested artifact names.
The initial direct-store cold import encountered the existing control-service cycle;
initializing `polisyos.runtime.http.services.control` first is the executed successful
entry order. Its failure and successful replay outputs are both retained.

| Existing owner | Measured seam and design consequence |
| --- | --- |
| `ControlPlaneStore` | Outbox dedupes by the SQL unique `(topic, event_key)` identity, survives reopen, and has a distinct publication checkpoint. Same key with different payload returns the existing payload: CR1 must explicitly content-reconcile it. Add a public exact key reader over its existing private lookup; add no database or table. |
| `RuntimeIdempotencyStore` | A new instance returns `started` for the same pending reservation. Completed HTTP response replay is its contract; pending state is process-local. Reuse is inappropriate for durable worker ownership, and this task does not repair that already-owned behavior. |
| `RuntimeDiagnosticEventLog` | Canonical diagnostic envelope and CAS event publisher, with a separate event-id dedupe contract. It is not a response queue. The CR1 authoritative custody record is the SQL-unique outbox publication with exact CAS payload, avoiding a second log. |
| `FileSystemCAS` | Owns content-addressed artifacts and content-integrity readback. CR1 stores its candidate artifacts through this owner and verifies every referenced payload on read. |
| `AuthorityBoundary` | Canonical purpose-scoped boundary is reused, constrained to candidate/shadow response content and custody mechanics. It is not replaced by a local authority DTO. |
| `ControlWorker` / `acquisition_route_loop` | Existing job worker and acquisition-specific recovery retain their contracts. CR1 provides an executable package worker over its own outbox topic, with the exact same handler used in-process and in actual child-process kill tests; no new generic job scheduler. |

## Chosen mechanism and alternatives

Choose composition of the existing control outbox and CAS. A new response database
would duplicate the durable store; HTTP idempotency alone loses pending reservations
across process death. Neither alternative is chosen.

`submit` validates and content-binds the request and its embedded candidate charter,
stores the CAS object, then enqueues an exact request handle. Request identity is
tenant/cell/request identity; a duplicate with changed bytes fails closed. The receipt
is returned only after durable enqueue. A lost reply can be retried using the same
request. A CAS object written before enqueue is an orphan candidate, not admission.

The worker reloads those exact bytes, validates the boundary and empty signer again,
and produces a deterministic failed-safe decision naming the required role. The
decision has no protected-action capability. Its publication is an immutable,
deduplicated outbox record that references its CAS bytes. Only afterwards does the
worker commit the request checkpoint. Recovery reconciles an existing decision by
content and returns it; no repeated irreversible custody publication occurs.

The snapshot reader independently reloads request and decision, exposes terminal
`failed_safe`, conservative `no_authority_expansion`, named missing role, decision
handle and escalation clock. Submitted/observed/effective/escalation times remain
distinct; advancing time can make escalation due but cannot authorize anything.
Restart evidence is content-bound to that exact prior decision, persisted and read
as candidate evidence; it cannot reopen the transition or turn alert disappearance
into renewed authority. E/X/V/C values travel as candidate context without defining
the constrained-product engine (`GY-CR2`) or adding Atlas lifecycle statuses.

The write-side queue lock is SQL uniqueness, not Python process memory. Competing
enqueue attempts reconcile the existing exact row after a uniqueness race. Consumer
readback validates identity and content before accepting either request or decision.
The property established is at-most-once **own custody publication** across actual
process death and duplicate delivery. External exactly-once execution is not claimed:
external execution is `integrate`, and no appointed signer or authorized action exists.

## Falsifiers and intended files

Write the `WP-08` negative first: an unsigned request must reach `failed_safe`, name
the missing role, expose a running escalation clock and never acquire a signer.
Then demonstrate real process `SIGKILL` at both (a) durable request before processing
and (b) decision publication before checkpoint, followed by a new process and an
actual repeated delivery. An independent direct SQL count of the complete request-key
decision publication denominator must be one, with a matching CAS decision readback.
The parent waits for an actual durable marker before sending SIGKILL; return code
must show the signal. No fake interruption result can satisfy this proof.

Other negatives: same id/different bytes; corrupt CAS request/decision; unknown
outbox kind; forged `model_construct`/`model_copy` signer or widened boundary at
intake; clock expiration as false approval; restart without the exact prior decision;
and removal of durable dedupe while keeping names/markers. Audit readback is the
surface; HTTP/Atlas presentation is `surface_out_of_scope`, assigned to the existing
Atlas projection integration without claiming that UI is wired here.

Planned Stage-2 mechanism write set:

- `src/polisyos/runtime/quality/adaptation_transition.py`: function-named candidate
  orchestration, four requested shapes, charter, durable handler and package worker.
- `src/polisyos/runtime/http/services/control_plane_store.py`: public exact outbox-key
  lookup delegating to the existing owner; exclusively assigned to B.
- `tests/unit/runtime/quality/test_adaptation_transition.py`: actual owner, child
  process and falsifier tests.

Mandatory companions are this decision, B journal/receipts, and a release fragment.
Root alone updates `runtime/quality/README.md`; root owns `runtime/quality/__init__.py`
and no facade export is requested. CB1 writes are disjoint. Each gate runs alone with
venv first in PATH; only named tests run. Existing targeted control-store importer
tests cover the public lookup extension. No debt/ledger write or compiler is allowed;
the default architecture gate is `not_completed`, not passed or skipped.

## Pattern and version pass

`P01/P02/P03`: build the complete request → CAS/outbox → handler → decision → snapshot
audit chain, with the UI limit explicit. `P05/P09/P15`: consumer-enforced candidate
boundary, typed absent signer and clock. `P27`: extend the outbox/CAS/boundary owners.
`P29/P32/P33/P37/P38`: real interruption, direct complete SQL denominator, corrupt
content and changed decisive-property probes. `P13`: no ERP, notification channel or
external executor. Existing owner seam limitations above are observations, not repairs.

Before execution the CR1 chain is `producer_missing`, `artifact_missing`,
`bridge_missing`, `consumer_missing`, `verification_missing`, `semantic_test_missing`.
The institutional signer remains `absent/unallocated` after execution. No existing
path is replaced or subordinated, so no `StrangleReceipt` is asserted or fabricated;
if the write set changes to replace a path, §3.5.5 applies before that change.

This is an additive internal schema family (`polisyos.runtime.adaptation_transition.v1`).
No existing governed epoch transition is intended. If a deciding gate establishes an
epoch impact, the transition must be declared from the lane's immutable merge base,
not from a workstream start, before its writer runs. No receipt-bearing epoch is
silently reissued.

## Execution order

1. Add `test_unsigned_request_fails_safe_and_names_role` in the named test file,
   run that exact test and preserve its absent-mechanism failure.
2. Add remaining falsifiers to the same file before their mechanism: actual killed
   worker/delivery replay, conflicting request, forged authority, corrupt CAS,
   clock expiry, restart binding. Keep child barriers in test utilities, not in
   production authority constructors.
3. Add the minimal public key reader and candidate response module; run the exact
   unsigned-request test to green, then the entire explicitly named CR1 file.
4. Run the existing
   `tests/unit/runtime/http/test_control_plane_store.py::test_control_plane_store_tracks_worker_leases_and_outbox`
   importer test. Run Ruff on the exact changed Python paths.
5. Remove the decisive content/dedupe property in an isolated import copy while
   retaining the fields and names; the unchanged matching negative must fail.
   Preserve complete output and remove no user files. Reopen the pattern register,
   record the final readback and all residuals, then hand root the frozen write set
   for its serialized commit and integrated review.

## Stage-2 architecture amendment: preserve governed owner bytes

The pre-edit scan found `module:polisyos.runtime.http.services.control_plane_store`
as a `decisive: true` member in
`architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json`.
**The proposed public-reader edit is withdrawn before implementation.** The architect
ruled that CR1 may consume the existing `_get_outbox_event_by_key` method through one
documented internal Runtime composition seam; known event IDs use the public getter.
This is owner reuse, not a duplicate query or database. No store source is changed,
and its existing governed bytes remain intact. Exact SQL/conflict/concurrent-delivery
tests exercise the seam without capped list enumeration. The complete recorded
member-path and dotted-identity denominator is checked at closeout; the initial
literal search alone is not treated as a zero-impact proof.

Review refinement (`P08`, one new temporal class): snapshot readback rejects a
request observation, decision publication, restart receipt or restart observation
that is later than `as_of`. Restart references carry `not_supplied`,
`current_candidate` or `expired_candidate`; none licenses reopening. Historical
reconstruction before an already-published decision is explicitly refused rather
than projecting future availability. This is a bounded audit reader, not the
whole-history temporal engine.

Measured concurrency refinement: the existing CAS ownership index uses only a
per-instance thread lock. Two CR1 store instances writing distinct request bytes
concurrently lost one ownership entry (`raw/verify-final.txt`, `ArtifactOwnershipError`),
before reaching the outbox. CR1 therefore reuses Fabric's existing
`atomic.file_lock` around **only CAS put plus immediate readback**, at
`<cas-root>/artifacts/ownership/adaptation-transition.lock`; outbox operations remain
concurrent. No CAS owner source is edited. The guarantee is bounded to cooperating
CR1 writers in that local CAS root. Foreign writers ignoring the lock remain a
CAS-ownership integration residual and can fail closed; their cross-owner safety is
not claimed. Platforms without the real process lock are refused.
