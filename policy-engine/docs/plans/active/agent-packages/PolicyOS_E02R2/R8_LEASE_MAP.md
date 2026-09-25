# R8 DUR-02 guarded lease-fence map

## Scope and evidence boundary

This is a read-only source map for the DUR-02 stale-worker regression. It was
prepared while the four-base baseline wave was active. No source or test code
was changed, and no tests or native jobs were run. The inspected code blobs on
the current R2 line are:

- **Source:** policy-engine/src/polisyos/runtime/http/services/control_plane_store.py
  at blob `4a49eef3c1d7da25e40436c0346778e28df13034`.
- **Test:** policy-engine/tests/unit/remediation/test_dur_02.py at blob
  `83c37356e6d694fc0960e272332660431712ec6a`.

The later R8 implementation candidate has exactly two code write paths:

1. policy-engine/tests/unit/remediation/test_dur_02.py — first, add a
   production-proxy stale-takeover witness and current-owner control.
2. policy-engine/src/polisyos/runtime/http/services/control_plane_store.py —
   replace the handler fence's thread-local transport with a per-store
   ContextVar and token reset.

resilience.py, control_worker.py, and run_lifecycle.py already provide the
production composition and context propagation needed for this repair. They
are not part of the proposed write set.

## Property and production call path

**Property.** Once a worker's (job_id, worker_id, attempt) lease is replaced
or expires, that worker cannot write terminal state or progress over the new
owner's job. A worker holding the live attempt can complete normally.

1. RuntimeContainer.startup lazily constructs ControlPlaneService when the
   container has no supplied control service
   (src/polisyos/runtime/http/container.py:347–373). ControlPlaneService.__init__
   constructs ControlPlaneStore and wraps it with guard_runtime_control_store(...)
   when no store is injected
   (src/polisyos/runtime/http/services/control/run_lifecycle.py:1403–1416).
   In embedded-worker mode it passes that same proxy to ControlWorker, with
   _process_control_job as the handler (:1565–1572).
2. ControlWorker.dispatch_once heartbeats and obtains the lease through
   self._store.lease_next_job(...) (src/polisyos/runtime/http/services/control_worker.py:148–165).
   The returned record carries the current attempt. The worker starts a
   separate renewal thread; it renews with explicit worker_id and
   expected_attempt (:193–217). That renewal path does not need the ambient
   handler fence.
3. _run_with_lease_heartbeat obtains job_execution_fence, enters it with
   the leased job ID, worker ID, and attempt, then invokes the handler inside
   the context (control_worker.py:193–256, fence entry at :247–254). The
   only production job_execution_fence caller found under src/polisyos is
   this ControlWorker path.
4. ControlPlaneStore.job_execution_fence rereads the job and refuses entry
   unless state is running, owner and attempt match, and expiry is in the
   future (src/polisyos/runtime/http/services/control_plane_store.py:1292–1329,
   checks at :1312–1324). It currently stores the tuple in
   threading.local at :1277 and clears it in finally at :1329.
5. The handler writes through the same self._control_store proxy. Its
   production calls include progress, completion, and failure at
   run_lifecycle.py:2367, 3083, 3238, 3374, 3428, 3476, 4082.
   GuardedDependencyProxy.__getattr__ wraps callable methods and routes each
   through BlockingDependencyGuard.run
   (src/polisyos/runtime/http/resilience.py:253–276). The guard copies the
   caller's context before submitting work to its executor (resilience.py:92–130,
   specifically copy_context() at :120 and context.run at :130). Nested direct
   store calls inside one guarded attempt stay on that executor worker
   (:98–112).

job_execution_fence uses @contextmanager. The proxy call returns the
context-manager object; its generator body is entered and exited by
ControlWorker on its synchronous dispatch thread. The context is therefore
set on that caller thread, and each proxied lifecycle method copies the bound
ContextVar into the executor. The token must be reset in the same context that
entered the synchronous context manager.

## Fenced lifecycle writes and the stale-worker hole

_resolve_job_execution_fence is called by exactly three lifecycle methods:

- complete_job (control_plane_store.py:2994–3019, resolution at :3006).
- fail_job (:3080–3100, resolution at :3088).
- update_progress_state (:3202–3217, resolution at :3212).

For a bound tuple, _job_fence_where requires the job to remain running, owned
by the same worker and attempt, and unexpired (control_plane_store.py:1361–1376).
_require_fenced_write raises ControlJobLeaseLostError when a bound update
does not affect exactly one row (:1378–1388; error type at :965–966).
Completion/failure/progress and their associated rows are performed through
the lifecycle transaction. Lease renewal is a separate explicit check:
renew_job_lease filters by running state, owner, unexpired lease and, when
provided, attempt (:3268–3295).

The decisive divergence occurs when the bound callback runs through the
production proxy. threading.local is empty on the guard executor thread, so
_resolve_job_execution_fence returns None (:1331–1359). With no fence,
_job_fence_where falls back to job_id = ? only (:1369–1370), and
_require_fenced_write does not reject the write (:1386). An already-running
old handler can therefore resume after a takeover and complete the new
worker's job. The current test uses a raw store and starts the stale worker
only after takeover (tests/unit/remediation/test_dur_02.py:88–122): it is
refused at context entry, before its handler attempts the terminal write, so
it does not exercise this executor-thread hole.

## Minimal ContextVar change

In control_plane_store.py, import ContextVar from contextvars, and keep
threading for the store lock and unrelated thread-local transaction. Replace
only _job_execution_fence with a per-instance context variable:

~~~python
self._job_execution_fence: ContextVar[tuple[str, str, int] | None] = ContextVar(
    "control_job_execution_fence", default=None
)
~~~

At context-manager entry, read it with .get() for the existing nested-fence
check. After the current lease reread passes, set the exact tuple and retain
the token:

~~~python
token = self._job_execution_fence.set((job_id, worker_id, attempt))
try:
    yield
finally:
    self._job_execution_fence.reset(token)
~~~

In _resolve_job_execution_fence, use .get() and preserve the current
job/owner/attempt consistency checks. Set only after the lease read succeeds;
reset the token rather than setting None, so exceptions restore the prior
context value. Do not change _human_decision_transaction, the explicit
renewal checks, or lifecycle method signatures.

This makes ContextVar a transport for the fence tuple, not authority. The
entry check rereads the stored lease, and the final SQL predicate still
recomputes running state, owner, attempt, and current expiry atomically at the
write boundary.

## Behavioral test, controls, and removal probe

Keep the current raw-store case as a control: on one handler thread, the
existing thread-local is visible and a stale finalization is refused. Add the
decisive case to the same test file using guard_runtime_control_store(raw)
and route both ControlWorker instances and their handler writes through that
proxy:

1. Create a job in the raw store and lease attempt 1 to worker A.
2. Start worker A's _run_with_lease_heartbeat in a test-owned thread. Its
   handler signals that it has entered after the lease fence is set, then
   waits on an event before calling guarded.complete_job(job_id=...).
3. From the test thread, expire A's lease through the raw store and lease the
   same job to worker B. Confirm the persisted row is running under B at
   attempt 2. Resume A's handler.
4. Capture A's raised ControlJobLeaseLostError; assert the job remains
   running, owned by B, at attempt 2. This is the guarded-store stale-worker
   negative.
5. Run B's attempt-2 ControlWorker through the same proxy and complete the
   job. Assert completed state and cleared lease. This is the
   property-preserving control: the live owner is not refused.

Use events and try/finally to release and join the test-owned thread. Keep
the takeover ahead of the old worker's next heartbeat (for determinism, set a
long test-only _heartbeat_interval_s; shutdown signals the pulse thread so
it need not wait for that interval). Do not let the old worker's heartbeat
renew attempt 1 between lease expiry and takeover.

**Marker-preserving removal probe.** After the ContextVar version passes,
preserve the test and its assertions but replace only the ContextVar storage
and reads/resets with the old thread-local behavior in an isolated,
sequential probe run. The guarded stale write should then complete B's row,
making the stale-refusal assertion turn red. Run no source edit while that
probe's test process is in flight. A raw-store-only pass is not a substitute
for this probe.

## P37 and P38 gate statement

- **Property:** a lifecycle write from a handler is admitted only for the
  exact lease generation that is still current at the write boundary.
- **Predicate and P37 classification:** (job_id, worker_id, attempt) is
  supplied by the runtime worker from the leased record; it is only a
  transport value. Currentness is **recomputed**: the store rereads and checks
  it before entering the handler, then the mutation's SQL predicate checks
  current running state, owner, attempt, and expiry again. The persisted row,
  not the ContextVar's presence or a marker, decides the write.
- **Implementation/property divergence (P38):** the intended property is
  exact-generation terminal/progress writes. The current implementation
  actually tests for a fence in the current OS thread. A guarded executor
  thread with no thread-local value is a divergent case: it falls back to
  job_id only and can finalize a replacement owner's job.
- **Distinguishing probe:** after the handler is already inside its valid
  attempt-1 fence, expire it and install attempt 2 before its guarded terminal
  call. A refusal proves the lease row, not the context marker alone, controls
  the result.

Pattern pass: P31 (one shared fence resolver protects all three lifecycle
write APIs), P29/P33 (execute the production proxy path and use the
marker-preserving removal probe), P37/P38 (recompute the decisive lease
predicate at the write and name the thread-local proxy divergence).

## Resource and verification sequence

No test command was run during this map. The four-base broker owns the
pre-repair replay for tests/unit/remediation/test_dur_02.py; confirm that file
is in its denominator before repair. Do not start a competing test while
that baseline wave is active.

After the baseline is complete and the broker releases a test slot:

- Run one focused pytest process for this file, with no xdist workers. The
  proxy uses the runtime's shared blocking executor; the test uses only a
  temporary SQLite database. It needs no production data, JAX, DuckDB, or
  other native job.
- Measure the first authorized wall time once, then set the alarm from that
  measured duration. Example invocation shape from policy-engine/:

  ~~~sh
  perl -e 'alarm shift; exec @ARGV' "$DUR02_TEST_TIMEOUT_SECONDS" \
    .venv/bin/python -m pytest tests/unit/remediation/test_dur_02.py -q
  ~~~

  DUR02_TEST_TIMEOUT_SECONDS is to be set from the measured run before
  execution; do not guess a timeout while the duration is unmeasured.
- Run the marker-preserving removal probe in its own sequential invocation
  with the same measured timeout. Do not edit the source tree while either
  run is in flight.
- Re-run the whole file at all four bases through the baseline broker after
  implementation. This remains one resource-bearing process group at a time;
  report each base's per-test outcome and attribute any pass-to-fail change.

The test-first order and one focused process keep the evidence tied to the
actual class while staying within the existing compute budget. The global
baseline and root's later explicit test-slot authorization take precedence
over this proposed sequence.
