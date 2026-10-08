# F query selector worker-resolution diagnosis

## Finding

The query/CAS consumer property remains **UNRUN**. The selector stops in `_fit_real` at `assert not result.issues`, before `RunCausalQueriesNode`, `_load_bound_query_result()`, `verify(ref)`, or the six peer-projection controls. A new direct producer diagnostic now establishes why the worker refuses the run: its locked execution profile requires Linux, while this local host is Darwin. This is an environment/profile limitation, not evidence of a source-class regression or a failed CAS-consumer assertion.

## Candidate and profile resolution

- Exact candidate: `556329c9cdd183197e644299381550f81f061620`, tree `a7a581044ee5c9e91b8c514c9aad4ff3051ce6a5`.
- Candidate archive root: `native-D/candidate`; it has no `.git` metadata. The candidate bridge `_dowhy_worker.py` resolves to the candidate's `policy-engine/workers/dowhy-014` profile. Its six required assets and candidate-local `.venv/bin/python` are present. The resolver does not depend on `.git`; the archive layout is not the cause.
- The app interpreter is the G `.venv` Python 3.14.3. The selector fixture configures the candidate worker's Python 3.12.12; the exact environment receipt reports DoWhy 0.14 and lock-consistent installed distributions. This app/worker split is intended.

## Direct producer evidence and cause

`producer-diagnostic/diagnose.py` imports the test helper from the exact candidate and invokes its existing `_fit_real` fixture with 100 rows. It does not call the query consumer. `producer-diagnostic/assessment.json` captures the actual `JobResult.issues` entry:

`DoWhy worker rejected/failed request: ValueError: locked Python3.12/DoWhy0.14 profile required`

The diagnostic script exits 0 because it successfully records the producer error; its recorded producer outcome is `ERROR`, not `PASS`. The stdout dispatch record shows `WorkerUnavailableError`. `producer-diagnostic/origin-audit.json` reports 795 candidate modules, no origin-audit errors, and the live product roots removed, tying the diagnostic to this candidate rather than G's live source tree.

The candidate's `workers/dowhy-014/worker.py:232-241` validates the request, then requires Python 3.12, `sys.platform == "linux"`, and DoWhy 0.14 before it calls `linear_ate()` or `gcm_fit()`. The two version checks match the recorded environment; the local Darwin platform fails the Linux-only check. `_dowhy_worker.run_worker()` wraps the worker's nonzero stderr as the observed `WorkerUnavailableError`. Thus the refusal occurs before estimator fitting. This confirms a platform/profile guard, not a CAS consumer failure.

The prior raw selector receipt contains only `WorkerUnavailableError` (one failed test, zero errors) and a 72.59 ms selection-history row. The new direct diagnostic adds the actual issue text and the source-level discriminator. The earlier trace-observer attempt was a **harness error**: pytest collected zero tests and the observer recorded zero events, so it supplies no cause evidence. The separate SciPy `dyld` import diagnostic is not the cause of this captured target failure; the target worker returned the explicit platform guard error before entering its estimator function.

**Disposition:** profile resolution/assets `PASS`; environment metadata `PASS`; native worker request `REFUSED_BY_LINUX_ONLY_PROFILE_GUARD_ON_DARWIN`; F query/CAS consumer property **UNRUN**. No product-code defect is established. The deciding consumer selector needs an execution host that satisfies the declared Linux worker profile; repeating it on this Darwin host cannot establish the consumer property.
