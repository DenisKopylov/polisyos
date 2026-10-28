# Verify control cancellation under saturated compute

This test-owned witness qualifies event-held control capacity only. It uses a real worker,
a configured synthetic identity/permission, the actual cancellation route, persisted
row/event/outbox and fresh store/HTTP consumers. It does not grant deployed permission,
prove native fit overlap, establish physical termination, reopen G's accepted configured
outer permit/serial folds, or close E02/G27-05/B56.

The two exact new source-definition nodes are:

```text
tests/unit/runtime/http/test_e02_saturated_control_cancellation.py::test_authenticated_cancellation_advances_while_compute_is_saturated[queued]
tests/unit/runtime/http/test_e02_saturated_control_cancellation.py::test_authenticated_cancellation_advances_while_compute_is_saturated[cancelled-queued]
```

Actual pytest collection remains the deciding set. Each node spawns its own fresh process
because the shared executor is process-wide. The owner profile is capacity=1, queue=1,
revision=c96-real-saturation-r1. A second Future must first be accepted pending; the
cancelled-queued variant then cancels that queued Future while retaining its bounded queue
reservation. Actual queue/physical-owner counts and a rejected third submission establish
full admission. The test never swallows rejection of the required second submission.

Prepare a unique output directory and an initially empty private PYTHONPYCACHEPREFIX for
each positive/removal/restored process. Admit the VM separately: disk total/free/inodes,
available RAM and cgroups, CPU quota, supported backend and the existing environment. A
32 GB disk is not a RAM promise. Use one measured numerical profile at a time, and keep
OMP_NUM_THREADS, OPENBLAS_NUM_THREADS, MKL_NUM_THREADS and NUMEXPR_NUM_THREADS at 1 for
numerical phases. Do not reinstall a working environment or upload private production data.

From the exact checkout's policy-engine/ directory, use the existing .venv Python and
normal pytest.ini/plugins through this supported file entrypoint. Do not rely on direct
`python -m pytest`, incidental PYTHONPATH or an installed `tests` package to bootstrap C96:

```text
.venv/bin/python -B tests/_helpers/e02_c96_control_harness.py --observe-pytest -o cache_dir=<phase>/pytest-cache --benchmark-storage=file://<phase>/benchmarks --basetemp <phase>/pytest-temp --junitxml=<phase>/pytest.xml --tb=short --color=no --maxfail=0 <one exact node above>
```

The helper derives product/src/tests roots from its own file before pytest import. It
explicitly binds the checkout's namespace `tests` directory, because a root sys.path entry
alone can lose to an installed regular `tests` package. An already-loaded foreign tests
module is a setup refusal, never silently replaced. The fresh spawn reconstructs this same
file as __mp_main__ before unpickling its canonical tests._helpers target, so it repeats the
same bootstrap independently. Parent and child record those exact roots, namespace paths
and entry-module names. No environment or pytest/plugin/profile override performs this fix.

Set POLISYOS_C96_EVIDENCE_DIR=<phase>/evidence and exact
POLISYOS_C96_EXPECTED_HEAD/POLISYOS_C96_EXPECTED_TREE to the committed candidate source.
The observer requires an empty private pycache prefix, -B, normal plugin discovery and no
unapproved PYTEST_ADDOPTS. Record the full command/cwd, quiet stdout/stderr, JUnit and
external process-tree RSS/disk/wall data with the retained supervisor. The helper records
actual pytest PID/config/plugins/collected nodes and each child's actual interpreter,
flags/env, PID/thread/timestamps, queue/control callbacks and loaded-source hashes. Its
finite loaded Python set is checked against Git; binary dependencies, unseen modules and
other data remain explicitly outside that check. Metadata presence is not backend loadability.

For each parameter use fresh positive, removal and restored processes on the same source
and profile. Only in removal set POLISYOS_C96_REMOVE_CONTROL_WRITE_CAPACITY=1. This test
seam routes the actual cancel_job write through a real guard with the same timeout,
breaker and exception policy onto the already full compute owner. Authentication and
resource-binding reads retain their actual dedicated control route. A current bound
authority must reach the real cancellation entry; its callback, owner file/hash and
actual method invocation are recorded. Process exit restores the fixture intervention.

Every phase executes the identical persisted-cancellation assertion before checking an
HTTP status marker. The expected removal red is the actual durable row remaining running,
with no cancelled source/outbox, after valid request binding. A 403 before that entry,
fixture/catalog/import/source mismatch, timeout or missing output is not this discriminator.
The positive also checks independent wrong-scope/permission/rollout/stale-attempt/body-proof
negatives with zero protected effects, an idempotent request, and late progress, manifest
and terminal refusals from the original worker's actual execution fence.

The selected Catalog fixture is candidate-only synthetic data. The app's selected source,
a fresh real resolver and an actual availability reader must agree on its content identity.
The fixture does not become production provenance or currentness.

Deliver only exact regular files needed to decide: changed tests/docs, small receipt,
complete stdout/stderr/JUnit, parent/child observations/readsets and measured resource logs.
Use lossless compression for large individual logs. Do not include pytest temp trees,
fixture catalogs, CAS, DBs, caches, dependencies, environments or source copies. An ignored
cloud path plus SHA is unavailable evidence until the coordinator obtains and hash-checks
its bytes. A delivery failure identifies the narrow missing proof; it does not mandate an
automatic local replay of all cloud work.

Expiry/takeover and native fit overlap are separate proofs. Existing C11/current store
selectors can supply bounded inputs for expiry, and test_fit_01.py names the actual supported
fit API/backend. Neither an old source-qualified C11 PASS nor a standalone fit result
establishes a new source's authenticated native fit-in-flight cancellation. Missing backend
or unproven overlap stays UNRUN/not_established; retain useful independent results.
